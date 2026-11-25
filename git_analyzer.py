"""Git Repository Architecture Analyzer for Frontend Architecture Advisor.

Clones a remote Git repository (or reads a local repository path), inspects its Angular / TypeScript
codebase, extracts architecture metrics (zoneless change detection, signal adoption, modularity,
memory leak risks, type safety), and compiles a complete architecture digest for the agent.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path


AUTH_FAILURE_PATTERNS = [
    "could not read username",
    "could not read password",
    "authentication failed",
    "terminal prompts disabled",
    "repository not found",
    "invalid username or token",
    "invalid username or password",
    "bad credentials",
    "saml enforcement",
    "sso",
    "403",
    "401",
    "forbidden",
    "unauthorized",
    "permission denied",
    "access denied",
    "access restricted",
]


def sanitize_err(msg: str, token: str = "") -> str:
    """Sanitize error messages to ensure tokens and credentials are never exposed."""
    # 1. Strip username:password from URLs
    msg = re.sub(r"(https?://)[^/@\s]+@", r"\1", msg)
    # 2. Redact raw and quoted token if provided
    if token:
        clean_tok = token.strip().strip("'\"")
        msg = msg.replace(clean_tok, "******")
        msg = msg.replace(urllib.parse.quote(clean_tok, safe=""), "******")
        msg = msg.replace(urllib.parse.quote(clean_tok), "******")
    return msg


def build_auth_candidates(git_url: str, token: str = "", username: str = "") -> tuple[list[str], str]:
    """Build candidate authenticated URLs to attempt for cloning.

    Returns:
        (candidate_urls: list[str], active_token: str)
    """
    url = git_url.strip()

    # Convert SSH URLs (git@host:owner/repo.git) to HTTPS for token authentication
    if url.startswith("git@"):
        m = re.match(r"^git@([^:]+):(.+)$", url)
        if m:
            url = f"https://{m.group(1)}/{m.group(2)}"

    # If URL already has credentials embedded (e.g. https://token@github.com/...), extract them
    m_cred = re.match(r"^(https?://)([^@]+)@(.+)$", url)
    if m_cred:
        proto, userinfo, rest = m_cred.group(1), m_cred.group(2), m_cred.group(3)
        if not token:
            if ":" in userinfo:
                u, p = userinfo.split(":", 1)
                if not username:
                    username = u
                token = p
            else:
                token = userinfo
        url = f"{proto}{rest}"

    if not token:
        return [url], ""

    token_clean = token.strip().strip("'\"")
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()

    user_clean = username.strip().strip("'\"")
    safe_token = urllib.parse.quote(token_clean, safe="")

    m_proto = re.match(r"^(https?://)(.+)$", url)
    proto = m_proto.group(1) if m_proto else "https://"
    host_path = m_proto.group(2) if m_proto else url

    candidates: list[str] = []

    # If user provided a specific username
    if user_clean:
        safe_user = urllib.parse.quote(user_clean, safe="")
        candidates.append(f"{proto}{safe_user}:{safe_token}@{host_path}")
        # Add fallback for GitHub fine-grained tokens which require 'oauth2'
        candidates.append(f"{proto}oauth2:{safe_token}@{host_path}")
    else:
        host_lower = host_path.lower()
        if "github.com" in host_lower:
            # Candidate 1: oauth2 (GitHub standard for fine-grained PATs & OAuth2)
            candidates.append(f"{proto}oauth2:{safe_token}@{host_path}")
            # Candidate 2: token:x-oauth-basic (GitHub classic token format)
            candidates.append(f"{proto}{safe_token}:x-oauth-basic@{host_path}")
            # Candidate 3: token:token
            candidates.append(f"{proto}{safe_token}:{safe_token}@{host_path}")
            # Candidate 4: x-access-token (GitHub App tokens)
            candidates.append(f"{proto}x-access-token:{safe_token}@{host_path}")
        elif "gitlab" in host_lower:
            candidates.append(f"{proto}oauth2:{safe_token}@{host_path}")
            candidates.append(f"{proto}{safe_token}:{safe_token}@{host_path}")
        elif "bitbucket" in host_lower:
            candidates.append(f"{proto}x-token-auth:{safe_token}@{host_path}")
            candidates.append(f"{proto}oauth2:{safe_token}@{host_path}")
        else:
            candidates.append(f"{proto}oauth2:{safe_token}@{host_path}")
            candidates.append(f"{proto}{safe_token}:{safe_token}@{host_path}")

    return candidates, token_clean


def inject_credentials(git_url: str, token: str = "", username: str = "") -> str:
    """Safely inject token/username into HTTP/HTTPS Git URLs for authenticated clone."""
    candidates, _ = build_auth_candidates(git_url, token, username)
    return candidates[0] if candidates else git_url


def _verify_access(candidate_urls: list[str], env: dict, timeout: int = 15) -> tuple[str | None, str]:
    """Fast credential check using `git ls-remote` (no data downloaded).

    Tries each candidate URL with a short timeout to find one that authenticates.
    Returns:
        (working_url | None, last_error_message)
    """
    last_err = "Unable to connect to remote repository."
    for url in candidate_urls:
        try:
            res = subprocess.run(
                ["git", "-c", "credential.helper=", "ls-remote", "--heads", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=timeout,
            )
            if res.returncode == 0:
                return url, ""
            last_err = res.stderr.strip() or res.stdout.strip() or last_err
            # If this is a clear auth failure, try the next candidate immediately
            err_lower = last_err.lower()
            is_auth_err = any(p in err_lower for p in AUTH_FAILURE_PATTERNS)
            if is_auth_err:
                continue
            # For non-auth errors (network, DNS, etc.), no point trying other candidates
            return None, last_err
        except subprocess.TimeoutExpired:
            last_err = "Repository access check timed out — verify network connectivity and VPN."
            continue
        except Exception as e:
            last_err = str(e)
            continue
    return None, last_err


def clone_repository(
    git_url: str,
    branch: str = "main",
    token: str = "",
    username: str = "",
    timeout_seconds: int = 180,
) -> tuple[bool, str, str, bool]:
    """Clone a Git repository into a temporary directory, with multi-strategy credential support.

    Two-phase approach:
      1. Fast access check via `git ls-remote` (finds the right auth format in seconds).
      2. Actual shallow clone using only the working URL (with generous timeout for large repos).

    Returns:
        (success: bool, path_or_error_message: str, branch_used: str, requires_auth: bool)
    """
    git_url = git_url.strip()
    branch = branch.strip()

    # Check if user provided a local directory path instead of a remote URL
    if os.path.isdir(git_url):
        return True, os.path.abspath(git_url), branch or "local", False

    candidates, active_token = build_auth_candidates(git_url, token, username)

    # Disable interactive terminal prompts and host credential helpers (e.g. osxkeychain)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}

    # ── Phase 1: Fast access verification via ls-remote ──
    working_url, verify_err = _verify_access(candidates, env, timeout=15)
    if working_url is None:
        clean_err = sanitize_err(verify_err, active_token)
        requires_auth = any(p in verify_err.lower() for p in AUTH_FAILURE_PATTERNS)
        return False, clean_err, branch, requires_auth

    # ── Phase 2: Shallow clone using the verified URL ──
    base_git_cmd = ["git", "-c", "credential.helper=", "clone", "--depth", "1", "--single-branch"]
    temp_dir = tempfile.mkdtemp(prefix="fe_arch_repo_")

    try:
        # Attempt with specified branch
        cmd = list(base_git_cmd)
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([working_url, temp_dir])

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=timeout_seconds,
        )

        if res.returncode == 0:
            return True, temp_dir, branch, False

        err_output = (res.stderr.strip() or res.stdout.strip()).lower()

        # If the branch doesn't exist, try the default branch
        is_branch_missing = "remote branch" in err_output and "not found" in err_output
        if is_branch_missing or (branch and res.returncode != 0):
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir = tempfile.mkdtemp(prefix="fe_arch_repo_")
            fb_cmd = ["git", "-c", "credential.helper=", "clone", "--depth", "1",
                       "--single-branch", working_url, temp_dir]
            res_fb = subprocess.run(
                fb_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=timeout_seconds,
            )
            if res_fb.returncode == 0:
                rev_res = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    text=True,
                )
                detected_branch = rev_res.stdout.strip() or "default"
                return True, temp_dir, detected_branch, False

            err_output = (res_fb.stderr.strip() or res_fb.stdout.strip()).lower()

        clean_err = sanitize_err(
            res.stderr.strip() or res.stdout.strip() or "Clone failed after access was verified.",
            active_token,
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        requires_auth = any(p in err_output for p in AUTH_FAILURE_PATTERNS)
        return False, clean_err, branch, requires_auth

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return (
            False,
            f"Git clone timed out after {timeout_seconds}s. The repository may be very large. "
            "Try cloning a specific branch with fewer files, or clone locally and point to the folder.",
            branch,
            False,
        )
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, sanitize_err(f"Error executing git clone: {str(e)}", active_token), branch, False


def scan_repository_architecture(repo_path: str, git_url: str = "", branch: str = "") -> dict:
    """Scan the repository directory and extract complete architectural health findings."""
    root = Path(repo_path)
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    ignore_dirs = {".git", "node_modules", "dist", ".angular", ".vscode", "coverage", "__pycache__", ".next", "build"}

    # 1. Find the Angular package.json — search root first, then subdirectories
    dependencies: dict[str, str] = {}
    dev_dependencies: dict[str, str] = {}
    angular_core_version = "Unknown"
    is_zoneless = False
    angular_project_root = root  # Where the Angular project actually lives

    def _try_read_package_json(pkg_path: Path) -> bool:
        """Try to read a package.json and return True if it contains Angular packages."""
        nonlocal dependencies, dev_dependencies, angular_core_version, angular_project_root
        try:
            with open(pkg_path, encoding="utf-8", errors="ignore") as f:
                pkg_data = json.load(f)
            deps = pkg_data.get("dependencies", {})
            dev_deps = pkg_data.get("devDependencies", {})
            peer_deps = pkg_data.get("peerDependencies", {})
            ang_ver = (
                deps.get("@angular/core")
                or dev_deps.get("@angular/core")
                or peer_deps.get("@angular/core")
                or deps.get("@angular/common")
                or dev_deps.get("@angular/cli")
                or ""
            )
            if ang_ver:
                dependencies = deps
                dev_dependencies = dev_deps
                angular_core_version = str(ang_ver)
                angular_project_root = pkg_path.parent
                return True
        except Exception:
            pass
        return False

    # Check root-level package.json first
    root_pkg = root / "package.json"
    found_angular = False
    if root_pkg.exists():
        found_angular = _try_read_package_json(root_pkg)

    # If root package.json doesn't have @angular/core, search subdirectories (monorepo support)
    if not found_angular:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            if "package.json" in filenames:
                candidate = Path(dirpath) / "package.json"
                if _try_read_package_json(candidate):
                    found_angular = True
                    break

    # Fallback: check package-lock.json if version is Unknown or workspace:*
    if angular_core_version in ("Unknown", "workspace:*", "*", "latest"):
        for search_root in (angular_project_root, root):
            lock_path = search_root / "package-lock.json"
            if lock_path.exists():
                try:
                    with open(lock_path, encoding="utf-8", errors="ignore") as f:
                        lock_data = json.load(f)
                    lock_ver = (
                        lock_data.get("packages", {}).get("node_modules/@angular/core", {}).get("version")
                        or lock_data.get("dependencies", {}).get("@angular/core", {}).get("version")
                    )
                    if lock_ver:
                        angular_core_version = str(lock_ver)
                        break
                except Exception:
                    pass
    ts_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for f in filenames:
            if f.endswith(".ts") and not f.endswith(".spec.ts"):
                ts_files.append(Path(dirpath) / f)

    total_ts_files = len(ts_files)

    # 3. Code patterns & metrics collection
    component_count = 0
    standalone_component_count = 0
    service_count = 0
    inject_api_count = 0
    constructor_di_count = 0
    signals_count = 0
    computed_count = 0
    signal_inputs_count = 0
    legacy_inputs_count = 0
    unmanaged_subscriptions_count = 0
    any_type_count = 0
    xss_bypass_count = 0
    storage_access_count = 0
    defer_blocks_count = 0
    onpush_strategy_count = 0
    has_app_config = False
    has_app_routes = False

    flagged_files: list[str] = []

    for path in ts_files:
        rel_path = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        low = content.lower()

        if "app.config.ts" in rel_path:
            has_app_config = True
            if "providezonelesschangedetection" in low:
                is_zoneless = True

        if "app.routes.ts" in rel_path or "routes.ts" in rel_path:
            has_app_routes = True

        if "@component" in low:
            component_count += 1
            if "standalone: true" in low or "standalone:true" in low or "standalone" not in low:
                standalone_component_count += 1
            if "changedetectionstrategy.onpush" in low:
                onpush_strategy_count += 1

        if "@injectable" in low:
            service_count += 1

        inject_api_count += len(re.findall(r"\binject\(", content))
        if "constructor(" in content:
            constructor_di_count += len(re.findall(r"constructor\s*\([^)]*private|constructor\s*\([^)]*public", content))

        signals_count += len(re.findall(r"\bsignal\(", content))
        computed_count += len(re.findall(r"\bcomputed\(", content))
        signal_inputs_count += len(re.findall(r"\binput(?:\.required)?\(", content))
        legacy_inputs_count += len(re.findall(r"@Input\(", content, re.I))
        defer_blocks_count += len(re.findall(r"@defer\b", content, re.I))

        # Antipatterns
        sub_matches = len(re.findall(r"\.subscribe\(", content))
        if sub_matches > 0:
            unmanaged_subscriptions_count += sub_matches
            flagged_files.append(f"{rel_path}: {sub_matches} subscription(s)")

        any_matches = len(re.findall(r":\s*any\b|\bas\s+any\b|any\[\]", content))
        any_type_count += any_matches

        xss_matches = len(re.findall(r"bypassSecurityTrust\w+", content))
        xss_bypass_count += xss_matches
        if xss_matches > 0:
            flagged_files.append(f"{rel_path}: bypassSecurityTrust used ({xss_matches} occurrences)")

        if "localstorage" in low or "sessionstorage" in low:
            storage_access_count += 1

    # 4. Build architecture observations for the Agent
    observations: list[str] = []

    # Architecture Strengths
    if standalone_component_count > 0:
        pct = int((standalone_component_count / max(component_count, 1)) * 100)
        observations.append(
            f"- Architecture Strengths: High standalone component adoption ({pct}% of {component_count} components), promoting modular tree-shaking and modern Angular architecture."
        )

    if signals_count > 0 or signal_inputs_count > 0:
        observations.append(
            f"- Architecture Strengths: Active adoption of Angular 21 reactive primitives with {signals_count} signals, {computed_count} computed expressions, and {signal_inputs_count} signal inputs."
        )

    if is_zoneless:
        observations.append(
            "- Architecture Strengths: Repository configured with provideZonelessChangeDetection() in application config, achieving modern zoneless execution and reducing bundle size."
        )
    elif onpush_strategy_count > 0:
        observations.append(
            f"- Code Quality: {onpush_strategy_count} components configured with OnPush change detection strategy, laying groundwork for zoneless migration."
        )

    # Code Quality
    if has_app_routes:
        observations.append(
            "- Code Quality: Dedicated route definitions found in app.routes.ts utilizing modern lazy-loaded route declarations."
        )

    if inject_api_count > 0:
        observations.append(
            f"- Code Quality: Found {inject_api_count} occurrences of modern functional inject() API for dependency injection."
        )

    # Architectural Risks
    if constructor_di_count > 0:
        observations.append(
            f"- Architectural Risks: Found {constructor_di_count} constructor-based parameter injections in components/services; recommend refactoring to functional inject() functions."
        )

    if legacy_inputs_count > 0:
        observations.append(
            f"- Architectural Risks: Found {legacy_inputs_count} legacy @Input() decorator usages; recommend migrating to modern signal inputs input() for fine-grained reactivity."
        )

    if any_type_count > 0:
        observations.append(
            f"- Architectural Risks: Detected {any_type_count} occurrences of untyped 'any' across TypeScript files, compromising compile-time safety and refactoring confidence."
        )

    if storage_access_count > 0:
        observations.append(
            f"- Architectural Risks: Direct browser storage (localStorage/sessionStorage) accessed in {storage_access_count} files without SSR platform abstraction guards."
        )

    # Critical Blockers
    if unmanaged_subscriptions_count > 0:
        observations.append(
            f"- Critical Blockers: Found {unmanaged_subscriptions_count} unmanaged Observable subscriptions without takeUntilDestroyed() or unsubscribe cleanup, creating high-risk memory leaks."
        )

    if xss_bypass_count > 0:
        observations.append(
            f"- Critical Blockers: Detected {xss_bypass_count} calls to DomSanitizer bypassSecurityTrust methods, introducing high-severity Cross-Site Scripting (XSS) security risks."
        )

    if not is_zoneless and "zone.js" in dependencies:
        observations.append(
            "- Architectural Risks: Architecture still relies on legacy Zone.js monkey-patching; recommend adopting zoneless change detection and signal effects."
        )

    # Refactoring Roadmap
    observations.append(
        "- Refactoring Roadmap: Refactor unmanaged subscriptions in flagged components using DestroyRef and takeUntilDestroyed()."
    )
    if defer_blocks_count == 0:
        observations.append(
            "- Refactoring Roadmap: Implement Angular @defer blocks for non-critical sub-components and heavy data tables to optimize Largest Contentful Paint (LCP)."
        )
    observations.append(
        "- Refactoring Roadmap: Enforce strict ESLint architectural boundaries to eliminate any types and decouple feature modules."
    )

    # Compile into full text
    digest_text = (
        f"Git Repository: {git_url or repo_path}\n"
        f"Branch: {branch or 'main'}\n"
        f"Angular Core Version: {angular_core_version}\n"
        f"Total TypeScript Source Files: {total_ts_files}\n"
        f"Components: {component_count} (Standalone: {standalone_component_count})\n"
        f"Services: {service_count}\n\n"
        + "\n".join(observations)
    )

    return {
        "git_url": git_url,
        "branch": branch,
        "angular_core_version": angular_core_version,
        "total_ts_files": total_ts_files,
        "component_count": component_count,
        "standalone_component_count": standalone_component_count,
        "service_count": service_count,
        "is_zoneless": is_zoneless,
        "unmanaged_subscriptions_count": unmanaged_subscriptions_count,
        "any_type_count": any_type_count,
        "xss_bypass_count": xss_bypass_count,
        "flagged_files": flagged_files[:10],
        "digest_text": digest_text,
    }
