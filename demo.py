"""Demo mode: frontend architecture advisor for TypeScript/Angular code using rule-based inspection.

Evaluates clean architecture principles, flags memory leaks and security vulnerabilities,
and produces a structured code health and architecture report without requiring an AI key.
"""
from __future__ import annotations

import re

SECTIONS = [
    "Architecture Strengths",
    "Code Quality",
    "Architectural Risks",
    "Critical Blockers",
    "Refactoring Roadmap",
]

COMPONENT_RE = re.compile(r"class\s+([A-Za-z0-9_]+)")
TICKET_RE = re.compile(r"\b([A-Z]{2,}-\d+)\b")


def demo_analyse(code: str) -> dict:
    """Analyze TypeScript/Angular code and return structured architecture recommendations."""
    findings = []
    low = code.lower()

    # Private / Secured Repository Gate Check
    if any(p in low for p in ["access restricted", "403 forbidden", "authentication failed", "repository not found", "permission denied"]) and ("private" in low or "credentials" in low or "secured" in low or "fatal" in low):
        return {
            "overall_verdict": "Critical Risks Detected",
            "status": "Red",
            "verdict_reason": "Access restricted: valid repository credentials required before starting review.",
            "status_reason": "Access restricted: valid repository credentials required before starting review.",
            "headline": "Authentication Required: Private or Secured Repository Detected.",
            "summary": "Repository access was denied or requires authentication. Architecture review cannot proceed without verified credentials.",
            "executive_summary": "Access to this secured repository is restricted. Please provide valid repository credentials (such as a Personal Access Token) before review can start.",
            "findings": [
                {
                    "section": "Critical Blockers",
                    "component_or_file": "Repository Authorization Gate",
                    "finding": "Repository access restricted by authentication gate. Review halted to prevent unauthorized analysis.",
                    "recommendation": "Provide a valid Personal Access Token (PAT) or deploy credentials with repository read permissions.",
                    "severity": "Critical",
                }
            ],
            "items": [
                {
                    "section": "Critical Blockers",
                    "text": "[Repository Authorization Gate] Access restricted — Fix: Provide valid Personal Access Token (PAT)",
                    "component": "Repository Authorization Gate",
                    "finding": "Access restricted",
                    "recommendation": "Provide valid Personal Access Token",
                    "severity": "Critical",
                    "owner": "Security",
                    "due": "",
                    "impact": "Critical",
                }
            ],
            "top_refactoring_actions": [
                {
                    "title": "Authenticate Repository Access",
                    "component": "Git Gateway",
                    "impact": "Unblocks architecture review with authorized read credentials."
                }
            ],
            "actions": [{"action": "Authenticate Repository Access", "owner": "Git Gateway", "why": "Unblocks review"}],
            "architectural_advisory_note": "Never attempt to speculate on or fabricate code findings for a private or secured repository without verified authorization. Please provide valid repository credentials.",
            "email": "Never attempt to speculate on or fabricate code findings for a private or secured repository without verified authorization. Please provide valid repository credentials.",
            "questions_for_team": ["Who is authorized to issue a repository Personal Access Token (PAT) for this architecture evaluation?"],
            "questions": ["Who is authorized to issue a repository Personal Access Token (PAT) for this architecture evaluation?"],
        }

    # Detect primary component or service name
    comp_match = COMPONENT_RE.search(code)
    target_comp = comp_match.group(1).strip() if comp_match else "Global"

    ticket_match = TICKET_RE.search(code)
    ticket_info = f" ({ticket_match.group(1)})" if ticket_match else ""

    # 1. Architecture Strengths
    if "signal(" in code or "computed(" in code or "input(" in code or "input." in code:
        findings.append({
            "section": "Architecture Strengths",
            "component_or_file": target_comp,
            "finding": "Adopts modern Angular 21 reactive signals, computed values, and signal inputs.",
            "recommendation": "Continue leveraging fine-grained signals to eliminate unnecessary component re-renders.",
            "severity": "Positive",
        })

    if "standalone: true" in code or "standalone:true" in code or ("standalone" not in code and "@component" in low):
        findings.append({
            "section": "Architecture Strengths",
            "component_or_file": target_comp,
            "finding": "Implemented as a standalone component, eliminating legacy NgModule coupling.",
            "recommendation": "Maintain standalone modularity to facilitate tree-shaking and route-level lazy loading.",
            "severity": "Positive",
        })

    # 2. Code Quality
    if "changedetectionstrategy.onpush" in low:
        findings.append({
            "section": "Code Quality",
            "component_or_file": target_comp,
            "finding": "Explicitly configured with OnPush change detection strategy.",
            "recommendation": "Maintains optimal change detection performance and simplifies future zoneless migration.",
            "severity": "Positive",
        })

    if "inject(" in code:
        findings.append({
            "section": "Code Quality",
            "component_or_file": target_comp,
            "finding": "Uses modern functional inject() API for clean dependency resolution.",
            "recommendation": "Standardize on functional inject() throughout all services and components.",
            "severity": "Positive",
        })

    # 3. Architectural Risks
    if "constructor(" in code and ("private http" in code or "private router" in code or "private sanitizer" in code):
        findings.append({
            "section": "Architectural Risks",
            "component_or_file": target_comp,
            "finding": "Constructor-based dependency injection mixes instantiating concerns with UI logic.",
            "recommendation": "Refactor constructor injections to modern inject() tokens for cleaner composition and testing.",
            "severity": "Medium",
        })

    if ": any" in code or "any[]" in code or "as any" in code:
        findings.append({
            "section": "Architectural Risks",
            "component_or_file": target_comp,
            "finding": "Pervasive usage of 'any' type bypasses TypeScript static analysis.",
            "recommendation": "Define strict TypeScript interfaces or domain models to prevent runtime type coercion errors.",
            "severity": "Medium",
        })

    if "sessionstorage" in low or "localstorage" in low:
        findings.append({
            "section": "Architectural Risks",
            "component_or_file": target_comp,
            "finding": "Direct browser storage access couples the component to the window object.",
            "recommendation": "Abstract storage access behind an injectable storage service with SSR platform checks.",
            "severity": "Medium",
        })

    # 4. Critical Blockers
    if ".subscribe(" in code and "takeuntildestroyed" not in low and "unsubscribe" not in low:
        findings.append({
            "section": "Critical Blockers",
            "component_or_file": target_comp,
            "finding": f"Unmanaged Observable subscription in component lifecycle{ticket_info} causes persistent memory leaks.",
            "recommendation": "Bind subscriptions using takeUntilDestroyed() or replace with Angular signals via toSignal().",
            "severity": "Critical",
        })

    if "bypasssecuritytrusthtml" in code:
        findings.append({
            "section": "Critical Blockers",
            "component_or_file": target_comp,
            "finding": "DomSanitizer bypassSecurityTrustHtml used with unsanitized dynamic markup.",
            "recommendation": "Remove security bypass; sanitize HTML using an approved Markdown parser or safe sanitization pipe.",
            "severity": "Critical",
        })

    if "getusermedia" in code and "ngondestroy" not in low and "destroyref" not in low:
        findings.append({
            "section": "Critical Blockers",
            "component_or_file": target_comp,
            "finding": "Hardware media stream initialized without teardown lifecycle hook.",
            "recommendation": "Register DestroyRef.onDestroy() callback to explicitly stop all active MediaStream tracks on disposal.",
            "severity": "Critical",
        })

    # 5. Refactoring Roadmap
    findings.append({
        "section": "Refactoring Roadmap",
        "component_or_file": target_comp,
        "finding": "UI component directly handles data fetching and side effects.",
        "recommendation": "Extract API and state handling into an isolated injectable Facade or Store service.",
        "severity": "High",
    })
    findings.append({
        "section": "Refactoring Roadmap",
        "component_or_file": target_comp,
        "finding": "Heavy child views and secondary widgets load eagerly in the initial bundle.",
        "recommendation": "Introduce @defer (on viewport) blocks to defer non-critical visual sections until scrolled into view.",
        "severity": "Medium",
    })

    risks = [f for f in findings if f["section"] == "Architectural Risks"]
    blockers = [f for f in findings if f["section"] == "Critical Blockers"]
    strengths = [f for f in findings if f["section"] == "Architecture Strengths"]

    if blockers:
        verdict = "Critical Risks Detected"
        status_color = "Red"
        verdict_reason = f"{len(blockers)} critical architectural blocker(s) identified that compromise stability or security."
    elif risks:
        verdict = "Needs Refactoring"
        status_color = "Amber"
        verdict_reason = f"{len(risks)} architectural smell(s) and tech debt items identified."
    else:
        verdict = "Production-Ready"
        status_color = "Green"
        verdict_reason = "Code adheres to modern clean frontend architecture standards."

    # Top refactoring priorities
    top_actions = []
    for b in blockers:
        top_actions.append({
            "title": f"Remediate: {b['finding'][:70]}",
            "component": b["component_or_file"],
            "impact": b["recommendation"]
        })
    for r in risks:
        if len(top_actions) < 3:
            top_actions.append({
                "title": f"Refactor: {r['finding'][:70]}",
                "component": r["component_or_file"],
                "impact": r["recommendation"]
            })

    questions = []
    if "getusermedia" in code and "ngondestroy" not in low:
        questions.append("What is the fallback strategy and permission flow for browsers or devices where camera access is denied?")
    if ": any" in code or "any[]" in code:
        questions.append("Are there defined backend OpenAPI/JSON schemas available to generate strict TypeScript models for this module?")
    if ".subscribe(" in code and "takeuntildestroyed" not in low:
        questions.append("Can this data stream be converted into a declarative Signal using toSignal() rather than manual subscription?")
    if not questions:
        questions.append("Are error boundaries configured at the route level to isolate component-level failures?")

    advisory_note = (
        f"Frontend Architecture Assessment for {target_comp}: Overall health is rated '{verdict}'. "
        f"Identified {len(strengths)} architectural strength(s), {len(risks)} risk(s), and {len(blockers)} critical blocker(s). "
        f"Immediate priority: {'Remediate memory leaks and security bypasses' if blockers else 'Address architectural coupling and type safety'}. "
        f"Adopt modern Angular 21 patterns (signals, functional inject, zoneless execution) for long-term maintainability."
    )

    # Backward compatibility mappings for existing report views
    items = []
    for f in findings:
        items.append({
            "section": f["section"],
            "text": f"[{f['component_or_file']}] {f['finding']} — Fix: {f['recommendation']}",
            "component": f["component_or_file"],
            "finding": f["finding"],
            "recommendation": f["recommendation"],
            "severity": f["severity"],
            "owner": f["component_or_file"],
            "due": "",
            "impact": f["severity"]
        })

    return {
        "overall_verdict": verdict,
        "status": status_color,
        "verdict_reason": verdict_reason,
        "status_reason": verdict_reason,
        "headline": f"{verdict}: {target_comp} review complete.",
        "summary": f"{len(findings)} architectural observations analyzed. {verdict_reason}",
        "executive_summary": f"Assessment for {target_comp} resulted in a verdict of {verdict}. {verdict_reason}",
        "findings": findings,
        "items": items,
        "top_refactoring_actions": top_actions[:3],
        "actions": [{"action": a["title"], "owner": a["component"], "why": a["impact"]} for a in top_actions[:3]],
        "architectural_advisory_note": advisory_note,
        "email": advisory_note,
        "questions_for_team": questions,
        "questions": questions,
    }
