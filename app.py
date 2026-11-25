"""Frontend Architecture Advisor: Clean Code & Modern Frontend Architecture Review.

Three Input Channels:
  1. 📁 File Upload & Code Review: Upload or paste an individual TypeScript/Angular file.
  2. 🌐 Git Repository Review: Clone and inspect complete repository architecture.
  3. 📚 Example Reviews: Curated Angular 21 TypeScript examples showcasing clean patterns and antipatterns.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import pandas as pd
import streamlit as st

from agent import run, to_markdown
from demo import SECTIONS
from git_analyzer import clone_repository, scan_repository_architecture
from prompts import SYSTEM_PROMPT

st.set_page_config(page_title="Frontend Architecture Advisor", page_icon="🏛️", layout="wide")


def setting(name: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets first, then from the environment."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default)).strip()


API_KEY = setting("AI_API_KEY")
BASE_URL = setting("AI_BASE_URL", "https://api.openai.com/v1")
MODEL = setting("AI_MODEL", "gpt-4o-mini")

STATUS_COLOUR = {
    "Green": "#16a34a",
    "Amber": "#d97706",
    "Red": "#dc2626",
    "Production-Ready": "#16a34a",
    "Needs Refactoring": "#d97706",
    "Critical Risks Detected": "#dc2626",
}

SECTION_ICON = {
    "Architecture Strengths": "🌟",
    "Code Quality": "✨",
    "Architectural Risks": "⚠️",
    "Critical Blockers": "⛔",
    "Refactoring Roadmap": "🛠️",
}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      .hero {background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: #fff; padding: 22px 26px;
             border-radius: 16px; margin-bottom: 18px;}
      .hero h1 {font-size: 1.7rem; margin: 0 0 4px 0; color: #fff;}
      .hero p {margin: 0; opacity: .88;}
      .card {background: #ffffff; color: #0f172a; border: 1px solid #e5e7eb; border-radius: 14px; padding: 14px 16px; margin-bottom: 12px;
             box-shadow: 0 1px 2px rgba(0,0,0,.04);}
      .card h4 {margin: 0 0 8px 0; font-size: 1.02rem;}
      .item {padding: 8px 0; border-top: 1px dashed #eef0f3; font-size: .95rem;}
      .item:first-of-type {border-top: none;}
      .comp-tag {display: inline-block; font-size: .78rem; font-weight: 600; padding: 2px 8px; border-radius: 6px; background: #e0f2fe; color: #0369a1; margin-right: 6px;}
      .sev-tag {display: inline-block; font-size: .72rem; font-weight: 700; padding: 1px 8px; border-radius: 999px; text-transform: uppercase;}
      .sev-Critical {background: #fee2e2; color: #b91c1c;}
      .sev-High {background: #ffedd5; color: #c2410c;}
      .sev-Medium {background: #fef3c7; color: #b45309;}
      .sev-Low {background: #f1f5f9; color: #475569;}
      .sev-Positive {background: #dcfce7; color: #15803d;}
      .status {display: inline-block; color: #fff; font-weight: 700; padding: 6px 14px; border-radius: 999px; font-size: 1rem;}
      .step {color: #0f172a; padding: 8px 12px; border-left: 4px solid #16a34a; background: #f8fafc; margin-bottom: 8px; border-radius: 6px;}
      .step.bad {border-left-color: #d97706;}
      .footer {color: #6b7280; font-size: .8rem; margin-top: 28px; text-align: center;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>🏛️ Frontend Architecture Advisor</h1>'
    "<p>Turn TypeScript code or a Git repository into a clear, one-page frontend architecture and code health report.</p></div>",
    unsafe_allow_html=True,
)

if API_KEY:
    st.caption(f"🟢 Connected to AI Model (`{MODEL}`)")
else:
    st.caption("ℹ️ Demo mode: running rule-based AST inspection. Add an AI API key in `.streamlit/secrets.toml` for deep semantic review.")

SAMPLES = {
    "Sample 1: Wealth Management Dashboard (Normal TS)": "samples/sample1.ts",
    "Sample 2: Clinical Workspace State Facade (Normal TS)": "samples/sample2.ts",
    "Sample 3: Storefront Checkout (Typos & Antipatterns TS)": "samples/sample3.ts",
    "Sample 4: User Status Badge (Very Short TS)": "samples/sample4.ts",
    "Sample 5: Unsafe Document Scanner (Missing Safeguards TS)": "samples/sample5.ts",
}


def read_file_safe(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


left, right = st.columns([1, 1.35], gap="large")

with left:
    tab_upload, tab_repo, tab_examples = st.tabs([
        "📁 File Upload Review",
        "🌐 Git Repository Review",
        "📚 Example Reviews",
    ])

    # ---------------- TAB 1: File Upload & Paste Code ----------------
    with tab_upload:
        st.markdown("#### Individual File Architecture Review")
        uploaded_file = st.file_uploader(
            "Upload TypeScript / Angular file (.ts)",
            type=["ts", "txt", "js", "tsx"],
            key="file_uploader",
            help="Upload a standalone component, service, state facade, or interceptor",
        )

        if "file_code_input" not in st.session_state:
            st.session_state.file_code_input = ""

        if uploaded_file is not None:
            try:
                uploaded_code = uploaded_file.getvalue().decode("utf-8", errors="ignore")
                if st.session_state.get("_last_uploaded_filename") != uploaded_file.name:
                    st.session_state.file_code_input = uploaded_code
                    st.session_state._last_uploaded_filename = uploaded_file.name
                st.caption(f"✅ Loaded `{uploaded_file.name}` ({len(uploaded_code.splitlines())} lines)")
            except Exception as e:
                st.error(f"Could not read uploaded file: {e}")

        st.text_area(
            "TypeScript Source Code",
            key="file_code_input",
            height=320,
            placeholder="Upload a .ts file above or paste TypeScript component/service code here...",
        )

        btn_col1, btn_col2 = st.columns([1, 2])
        with btn_col1:
            if st.button("Load Sample", use_container_width=True, key="btn_load_sample"):
                st.session_state.file_code_input = read_file_safe("samples/sample1.ts")
                st.rerun()
        with btn_col2:
            go_file = st.button("Review Code Architecture", type="primary", use_container_width=True, key="btn_file_review")

    # ---------------- TAB 2: Git Repository Review ----------------
    with tab_repo:
        st.markdown("#### Full Git Repository Architecture Review")
        repo_presets = {
            "Enterprise Wealth Portal (Sample Angular 21 Repo)": ("samples/sample_repo", "main"),
            "Custom Git Repository": ("", "main"),
        }
        chosen_preset = st.selectbox("Select Repository Preset", list(repo_presets.keys()))
        default_url, default_branch = repo_presets[chosen_preset]

        if "prev_repo_preset" not in st.session_state:
            st.session_state.prev_repo_preset = chosen_preset

        if st.session_state.prev_repo_preset != chosen_preset:
            st.session_state.prev_repo_preset = chosen_preset
            st.session_state.git_url_input = default_url
            st.session_state.branch_input = default_branch

        git_url_input = st.text_input(
            "Git Repository URL (or local repo path)",
            value=default_url,
            placeholder="https://github.com/organization/frontend-repo.git",
            key="git_url_input",
        )
        branch_input = st.text_input("Branch name", value=default_branch, placeholder="main", key="branch_input")

        # Secured / Private Repository Credential Inputs
        auth_expanded = st.session_state.get("show_auth_prompt", False) or bool(st.session_state.get("repo_token", ""))
        with st.expander("🔒 Repository Authentication (Required for Private Repositories)", expanded=auth_expanded):
            st.markdown("*Enter your Personal Access Token (PAT) below for private or enterprise repositories:*")
            st.text_input(
                "Personal Access Token (PAT) / Deploy Token",
                type="password",
                key="repo_token",
                placeholder="e.g. ghp_xxxxxxxx or glpat-xxxxxxxx",
                help="For GitHub: Use a token with 'repo' scope. For GitLab/Bitbucket: Use a Project Deploy Token or PAT.",
            )
            st.text_input(
                "Git Username (optional)",
                key="repo_username",
                placeholder="Leave blank for automatic detection (e.g. oauth2, x-oauth-basic)",
            )

        st.caption(
            "ℹ️ *The agent clones the repository, scans package.json, angular config, routes, components, and services, then produces a complete architectural health report.*"
        )
        go_repo = st.button("Clone & Review Full Architecture", type="primary", use_container_width=True, key="btn_repo_review")

    # ---------------- TAB 3: Example Code Reviews ----------------
    with tab_examples:
        st.markdown("#### Curated Angular 21 Examples")
        chosen_sample_name = st.selectbox("Select a sample architecture scenario", list(SAMPLES.keys()), key="sample_selector")
        sample_path = SAMPLES[chosen_sample_name]
        sample_code = read_file_safe(sample_path)

        with st.expander("Preview Sample Code", expanded=True):
            st.code(sample_code, language="typescript")

        go_sample = st.button("Review This Example Code", type="primary", use_container_width=True, key="btn_sample_review")


with right:
    # Trigger 1: File Upload / Paste Review
    if go_file:
        code_to_review = st.session_state.get("file_code_input", "").strip()
        if not code_to_review and uploaded_file is not None:
            try:
                code_to_review = uploaded_file.getvalue().decode("utf-8", errors="ignore").strip()
            except Exception:
                code_to_review = ""

        if not code_to_review:
            st.warning("Please upload a .ts file or paste TypeScript source code to review.")
        else:
            filename = uploaded_file.name if uploaded_file is not None else "TypeScriptComponent.ts"
            with st.spinner(f"Analyzing {filename} architecture, reactivity patterns, and potential leaks..."):
                try:
                    result, steps = run(code_to_review, SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL)
                    st.session_state.result, st.session_state.steps = result, steps
                    st.session_state.repo_meta = None
                    st.session_state.reviewed_file = filename
                except Exception as err:
                    st.error(f"Architecture review failed: {err}")
                    st.stop()

    # Trigger 2: Git Repository Review
    if go_repo:
        url_to_review = st.session_state.get("git_url_input", "").strip()
        branch_to_use = st.session_state.get("branch_input", "main").strip()
        repo_token = st.session_state.get("repo_token", "").strip()
        repo_user = st.session_state.get("repo_username", "").strip()

        if not url_to_review:
            st.warning("Please provide a Git repository URL or choose a preset.")
        else:
            with st.spinner(f"Connecting to {url_to_review} ({branch_to_use}) and verifying repository access..."):
                try:
                    success, repo_path_or_err, actual_branch, requires_auth = clone_repository(
                        url_to_review,
                        branch_to_use,
                        token=repo_token,
                        username=repo_user,
                    )

                    if not success:
                        st.session_state["show_auth_prompt"] = True
                        if requires_auth:
                            if not repo_token:
                                st.error(
                                    "🔒 **Private / Secured Repository Detected:** Access was denied or authentication failed.\n\n"
                                    "The agent will NOT start or guess an architecture review without verified access.\n\n"
                                    "👉 **Action Required:** Please enter your Personal Access Token (PAT) in the **🔒 Repository Authentication** section on the left and click **Clone & Review Full Architecture** again."
                                )
                            else:
                                err_lower = repo_path_or_err.lower()
                                if "saml" in err_lower or "sso" in err_lower:
                                    st.error(
                                        "🔒 **Organization SAML SSO Authorization Required:**\n\n"
                                        "Your Personal Access Token was rejected because your organization enforces SAML Single Sign-On (SSO).\n\n"
                                        "👉 **How to Authorize Your Token:**\n"
                                        "1. On GitHub, go to **Settings > Developer Settings > Personal access tokens**.\n"
                                        "2. Locate your token, click **Configure SSO** next to it, and click **Authorize** for your organization.\n"
                                        "3. Once authorized, click **Clone & Review Full Architecture** again."
                                    )
                                else:
                                    st.error(
                                        "🔒 **Authentication Failed for Private Repository:**\n\n"
                                        "Git could not authenticate with the provided credentials. Details from Git:\n\n"
                                        f"> `{repo_path_or_err}`\n\n"
                                        "👉 **Troubleshooting Checklist:**\n"
                                        "- **Token Expiration:** Confirm that your token is active and not expired.\n"
                                        "- **Token Permissions:** Ensure the token has `repo` scope (GitHub Classic PAT) or **Contents: Read-only** (GitHub Fine-Grained PAT).\n"
                                        "- **Username:** If you left the username blank, try entering your Git username in the optional username field."
                                    )
                        else:
                            st.error(f"Git Clone Error: {repo_path_or_err}")
                        st.stop()

                    # Authentication verified and clone succeeded!
                    st.session_state["show_auth_prompt"] = False
                    repo_report = scan_repository_architecture(repo_path_or_err, url_to_review, actual_branch)
                    if repo_path_or_err.startswith(tempfile.gettempdir()):
                        shutil.rmtree(repo_path_or_err, ignore_errors=True)

                    result, steps = run(repo_report["digest_text"], SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL)

                    st.session_state.result, st.session_state.steps = result, steps
                    st.session_state.repo_meta = repo_report
                except Exception as err:
                    st.error(f"Repository architecture review failed: {err}")
                    st.stop()

    # Trigger 3: Example Review
    if go_sample:
        selected_sample_code = read_file_safe(SAMPLES[chosen_sample_name])
        with st.spinner(f"Reviewing architecture for {chosen_sample_name}..."):
            try:
                result, steps = run(selected_sample_code, SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL)
                st.session_state.result, st.session_state.steps = result, steps
                st.session_state.repo_meta = None
            except Exception as err:
                st.error(f"Example review failed: {err}")
                st.stop()

    result = st.session_state.get("result")
    steps = st.session_state.get("steps", [])
    repo_meta = st.session_state.get("repo_meta")

    if not result:
        st.markdown(
            '<div class="card"><h4>How it works</h4>'
            '<div class="item"><b>1. File Upload Review:</b> Upload or paste a single TypeScript/Angular file for component/service-level architecture review.</div>'
            '<div class="item"><b>2. Git Repository Review:</b> Enter a Git repository URL and branch to clone and review full project structure, routes, and patterns.</div>'
            '<div class="item"><b>3. Example Reviews:</b> Explore curated Angular 21 samples showcasing modern signals, zoneless mode, and common anti-patterns.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        # Show repository metadata banner if a repository was reviewed
        if repo_meta:
            st.markdown(
                f'<div class="card" style="background:#f1f5f9;border-left:5px solid #2563eb;">'
                f'<b>🌐 Repository Architecture Scan:</b> <code>{repo_meta.get("git_url")}</code> (Branch: <code>{repo_meta.get("branch")}</code>)<br>'
                f'<span style="font-size:0.9rem;color:#334155">'
                f'Angular: <b>{repo_meta.get("angular_core_version")}</b> | '
                f'Source Files: <b>{repo_meta.get("total_ts_files")}</b> | '
                f'Components: <b>{repo_meta.get("component_count")}</b> (Standalone: <b>{repo_meta.get("standalone_component_count")}</b>) | '
                f'Zoneless: <b>{"Yes ✅" if repo_meta.get("is_zoneless") else "No (Zone.js)"}</b> | '
                f'Unmanaged Subs: <b>{repo_meta.get("unmanaged_subscriptions_count")}</b> | '
                f'XSS Bypasses: <b>{repo_meta.get("xss_bypass_count")}</b>'
                f'</span></div>',
                unsafe_allow_html=True,
            )
        elif st.session_state.get("reviewed_file"):
            st.markdown(
                f'<div class="card" style="background:#f0fdf4;border-left:5px solid #16a34a;">'
                f'<b>📄 Source File Reviewed:</b> <code>{st.session_state.get("reviewed_file")}</code>'
                f'</div>',
                unsafe_allow_html=True,
            )

        findings = result.get("findings", [])
        verdict = result.get("overall_verdict", "Needs Refactoring")
        colour = STATUS_COLOUR.get(verdict, STATUS_COLOUR.get(result.get("status", ""), "#6b7280"))

        st.markdown(
            f'<span class="status" style="background:{colour}">Verdict: {verdict}</span>'
            f'&nbsp;&nbsp;<span style="color:#475569;font-weight:500;">{result.get("verdict_reason", result.get("status_reason", ""))}</span>',
            unsafe_allow_html=True,
        )
        st.write("")

        # Executive Summary
        exec_summary = result.get("executive_summary", result.get("summary", ""))
        if exec_summary:
            st.markdown(
                f'<div class="card" style="border-left:5px solid {colour};"><h4>Executive Architecture Summary</h4>'
                f'<div style="font-size:1.02rem;color:#1e293b;">{exec_summary}</div></div>',
                unsafe_allow_html=True,
            )

        # Metrics bar
        count_by_section = lambda s: len([f for f in findings if f.get("section") == s])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Strengths", count_by_section("Architecture Strengths"))
        m2.metric("Code Quality", count_by_section("Code Quality"))
        m3.metric("Risks", count_by_section("Architectural Risks"))
        m4.metric("Blockers", count_by_section("Critical Blockers"))

        tab_rep, tab_reg, tab_road, tab_adv, tab_qst, tab_diag = st.tabs([
            "Architecture Report",
            "Risks & Vulnerabilities",
            "Refactoring Roadmap",
            "Advisory Note",
            "Questions for Team",
            "Review Diagnostics",
        ])

        # Tab 1: Architecture Report by Section
        with tab_rep:
            for s in SECTIONS:
                sec_findings = [f for f in findings if f.get("section") == s]
                body_parts = []
                for f in sec_findings:
                    comp = f.get("component_or_file", "Global")
                    sev = f.get("severity", "Medium")
                    rec = f.get("recommendation", "")
                    rec_html = f'<div style="margin-top:4px;color:#15803d;font-size:0.9rem;"><b>Clean Architecture Fix:</b> {rec}</div>' if rec else ""
                    body_parts.append(
                        f'<div class="item">'
                        f'<span class="comp-tag">{comp}</span>'
                        f'<span class="sev-tag sev-{sev}">{sev}</span><br>'
                        f'<div style="margin-top:4px;">{f.get("finding", "")}</div>'
                        f'{rec_html}'
                        f'</div>'
                    )
                body = "".join(body_parts) or '<div class="item" style="color:#64748b;">No findings in this section.</div>'
                st.markdown(f'<div class="card"><h4>{SECTION_ICON.get(s, "📁")} {s}</h4>{body}</div>', unsafe_allow_html=True)

        # Tab 2: Risks & Vulnerabilities Register
        with tab_reg:
            risk_blockers = [f for f in findings if f.get("section") in ("Architectural Risks", "Critical Blockers")]
            if risk_blockers:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Component / File": f.get("component_or_file", "Global"),
                            "Severity": f.get("severity", "Medium"),
                            "Architectural Issue": f.get("finding", ""),
                            "Clean Architecture Recommendation": f.get("recommendation", ""),
                        }
                        for f in risk_blockers
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("No architectural risks or critical blockers detected in the evaluated code.")

            if repo_meta and repo_meta.get("flagged_files"):
                st.markdown("**Flagged Repository Files with Potential Antipatterns:**")
                for ff in repo_meta["flagged_files"]:
                    st.markdown(f"- <code>{ff}</code>", unsafe_allow_html=True)

        # Tab 3: Refactoring Roadmap
        with tab_road:
            st.markdown("#### High-Priority Architectural Refactorings")
            actions = result.get("top_refactoring_actions", [])
            if actions:
                for idx, act in enumerate(actions, 1):
                    title = act.get("title", act.get("action", ""))
                    comp = act.get("component", act.get("owner", "Architecture"))
                    impact = act.get("impact", act.get("why", ""))
                    st.markdown(
                        f'<div class="step"><b>{idx}. {title}</b><br>'
                        f'<span style="color:#475569;">Target: <code>{comp}</code> &nbsp;·&nbsp; Impact: {impact}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.write("No urgent refactoring actions required.")

        # Tab 4: Advisory Note
        with tab_adv:
            st.markdown("#### Architectural Advisory Note for Tech Leads")
            advisory = result.get("architectural_advisory_note", result.get("email", "Not enough information."))
            st.text_area("Advisory Note", advisory, height=200, label_visibility="collapsed")

        # Tab 5: Questions for Team
        with tab_qst:
            st.markdown("#### Architectural Clarifications to Discuss with Engineering Team")
            questions = result.get("questions_for_team", result.get("questions", []))
            if questions:
                for q in questions:
                    st.markdown(f"- {q}")
            else:
                st.write("All architectural specifications, lifecycles, and boundaries are clear.")

        # Tab 6: Review Diagnostics
        with tab_diag:
            st.markdown("#### Agent Review Quality Gates")
            for idx, s in enumerate(steps, 1):
                st.markdown(
                    f'<div class="step {"" if s.get("ok") else "bad"}"><b>{idx}. {s.get("name", "")}</b> {"✓" if s.get("ok") else "!"}<br>'
                    f'<span style="color:#475569;">{s.get("detail", "")}</span></div>',
                    unsafe_allow_html=True,
                )

        st.download_button(
            "Download Architecture Review (.md)",
            to_markdown(result),
            file_name="frontend-architecture-review.md",
            use_container_width=True,
        )
        st.caption("🔒 Please verify that you have authorized repository access and review all recommendations before applying them.")

st.markdown('<div class="footer">Built by Vaibhav Vichare at Zero to Live, Future Proof India</div>', unsafe_allow_html=True)
