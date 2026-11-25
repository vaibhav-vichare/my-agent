"""The agent: plan, draft, check its own work, fix it, and ask about what is missing.

Specialized exclusively for Frontend Code Review and Clean Architecture Advisory.
"""
from __future__ import annotations

import json
import re
import time

from demo import SECTIONS, demo_analyse

FORMAT = """
Answer with ONE JSON object and nothing else, in exactly this shape:
{
  "overall_verdict": "Production-Ready" | "Needs Refactoring" | "Critical Risks Detected",
  "status": "Green" | "Amber" | "Red",
  "verdict_reason": "one concise sentence explaining the overall architecture health verdict",
  "executive_summary": "two clear sentences for the Senior Architect summarizing codebase health and top structural findings",
  "findings": [
    {
      "section": "Architecture Strengths" | "Code Quality" | "Architectural Risks" | "Critical Blockers" | "Refactoring Roadmap",
      "component_or_file": "file path, component, or service name referenced in the code, or 'Global'",
      "finding": "the specific architectural pattern or anti-pattern identified in the code",
      "recommendation": "the concrete clean architecture fix or modern Angular 21 pattern to apply",
      "severity": "Critical" | "High" | "Medium" | "Low" | "Positive"
    }
  ],
  "top_refactoring_actions": [
    {
      "title": "the most critical architectural refactoring",
      "component": "the target component, service, or module",
      "impact": "why this refactoring is critical for scalability, stability or performance"
    }
  ],
  "architectural_advisory_note": "a concise advisory note for the Senior Architect and Tech Leads (under 120 words) with key technical guidance",
  "questions_for_team": [
    "architectural questions to clarify with the engineering team (e.g. missing state boundaries, unhandled lifecycles, error strategies)"
  ]
}
Every observation must appear in exactly one finding. At most 3 top refactoring actions, most critical first.
Focus 100% on code architecture, patterns, memory leaks, and type safety. Do not include sprint deadlines, dates, or personal owner names.
"""

TOKEN = re.compile(r"\b[A-Z]{2,}-\d+\b")


def _json_from(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("The model did not return the report in the expected format.")
    data = json.loads(m.group(0))

    # Normalize fields
    for k in ("findings", "top_refactoring_actions", "questions_for_team"):
        data.setdefault(k, [])

    data.setdefault("overall_verdict", "Needs Refactoring")
    data.setdefault("verdict_reason", "")
    data.setdefault("executive_summary", "")
    data.setdefault("architectural_advisory_note", "")

    # Map status color from verdict
    verdict_low = data.get("overall_verdict", "").lower()
    if "production" in verdict_low or "ready" in verdict_low or "green" in verdict_low:
        data["status"] = "Green"
    elif "critical" in verdict_low or "blocker" in verdict_low or "red" in verdict_low:
        data["status"] = "Red"
    else:
        data["status"] = "Amber"

    data["headline"] = f"{data['overall_verdict']}: {data['verdict_reason']}"
    data["summary"] = data["executive_summary"]
    data["status_reason"] = data["verdict_reason"]
    data["email"] = data["architectural_advisory_note"]
    data["questions"] = data["questions_for_team"]
    data["actions"] = [{"action": a.get("title", ""), "owner": a.get("component", "Architecture"), "why": a.get("impact", "")} for a in data.get("top_refactoring_actions", [])]

    # Compatibility items
    items = []
    for f in data.get("findings", []):
        items.append({
            "section": f.get("section", "Code Quality"),
            "text": f"[{f.get('component_or_file', 'Component')}] {f.get('finding', '')} — Recommendation: {f.get('recommendation', '')}",
            "component": f.get("component_or_file", "Global"),
            "finding": f.get("finding", ""),
            "recommendation": f.get("recommendation", ""),
            "severity": f.get("severity", "Medium"),
            "owner": f.get("component_or_file", ""),
            "due": "",
            "impact": f.get("severity", "Medium")
        })
    data["items"] = items

    return data


def check(result: dict, notes: str) -> list[str]:
    """The quality checks for code review analysis. Returns problems found (empty list = all good)."""
    problems = []
    low_notes = notes.lower()
    findings = result.get("findings", [])

    # Check 1: Every finding belongs to one of the 5 valid architecture sections
    bad = [f for f in findings if f.get("section") not in SECTIONS]
    if bad or not findings:
        problems.append("Check 1: some findings are not in one of the 5 architecture sections." if findings else "Check 1: no architectural findings were produced.")

    # Check 2: No invented ticket numbers
    invented = []
    for f in findings:
        for tok in TOKEN.findall(f.get("finding", "") + " " + f.get("recommendation", "")):
            if tok.lower() not in low_notes:
                invented.append(tok)
    for a in result.get("top_refactoring_actions", []):
        for tok in TOKEN.findall(a.get("title", "") + " " + a.get("impact", "")):
            if tok.lower() not in low_notes:
                invented.append(tok)

    if invented:
        problems.append("Check 2: these ticket references do not appear in the input: " + ", ".join(sorted(set(invented))[:8]) + ".")

    # Check 3: If Critical Blockers are found, refactoring actions or clarifying questions must be asked
    blockers = [f for f in findings if f.get("section") == "Critical Blockers"]
    if blockers and not result.get("questions_for_team") and not result.get("top_refactoring_actions"):
        problems.append("Check 3: critical blockers were detected, but no refactoring actions or architectural questions were provided.")

    return problems


def _ask_model(client, model: str, system: str, user: str) -> str:
    reply = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return reply.choices[0].message.content or ""


def run(notes: str, system_prompt: str, api_key: str = "", base_url: str = "", model: str = "") -> tuple[dict, list[dict]]:
    """Run the architecture review agent. Returns (result, steps)."""
    steps: list[dict] = []

    def step(name: str, detail: str, ok: bool = True):
        steps.append({"name": name, "detail": detail, "ok": ok})

    t0 = time.time()
    if not api_key:
        result = demo_analyse(notes)
        step("Analyzed code architecture", f"{len(result.get('findings', []))} architectural findings evaluated (demo mode).")
    else:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url or None)
        system = system_prompt.strip() + "\n\n" + FORMAT
        result = _json_from(_ask_model(client, model, system, notes))
        step("Analyzed code architecture", f"{len(result.get('findings', []))} architectural findings evaluated by AI model in {time.time() - t0:.1f} s.")

    problems = check(result, notes)
    if not problems:
        step("Checked review quality", "All checks passed: clean categorization, grounded findings, and actionable recommendations.")
    else:
        step("Checked review quality", " ".join(problems), ok=False)
        if api_key:
            fix_user = (notes + "\n\nYour previous review:\n" + json.dumps(result) +
                        "\n\nIt failed these quality checks:\n- " + "\n- ".join(problems) +
                        "\n\nFix only these problems and answer again in the same JSON shape.")
            result = _json_from(_ask_model(client, model, system, fix_user))
            again = check(result, notes)
            step("Fixed review inconsistencies", "All checks pass now." if not again else "Still open: " + " ".join(again), ok=not again)
        else:
            step("Flagged review inconsistencies", "In demo mode inconsistencies are highlighted for inspection.", ok=False)

    q = len(result.get("questions_for_team", []))
    step("Formulated architecture questions", f"{q} question(s) framed for the engineering team." if q else "All architectural details clear.")
    return result, steps


def to_markdown(result: dict) -> str:
    """The architecture report as plain markdown, ready for download or copy."""
    verdict = result.get("overall_verdict", "Needs Refactoring")
    out = [
        f"# Frontend Architecture & Code Health Review: {verdict}",
        "",
        f"**Verdict Reason:** {result.get('verdict_reason', '')}",
        "",
        f"**Executive Summary:** {result.get('executive_summary', '')}",
        "",
    ]

    findings = result.get("findings", [])
    for s in SECTIONS:
        out.append(f"## {s}")
        rows = [f for f in findings if f.get("section") == s]
        if not rows:
            out.append("- No findings in this section.")
        for f in rows:
            comp = f"**[{f.get('component_or_file', 'Global')}]** " if f.get("component_or_file") else ""
            sev = f" *(Severity: {f.get('severity', '')})*" if f.get("severity") else ""
            out.append(f"- {comp}{f.get('finding', '')}{sev}")
            if f.get("recommendation"):
                out.append(f"  *Clean Architecture Fix:* {f.get('recommendation')}")
        out.append("")

    if result.get("top_refactoring_actions"):
        out.append("## Top Refactoring Priorities")
        for i, a in enumerate(result["top_refactoring_actions"], 1):
            out.append(f"{i}. **{a.get('title', '')}** (Component: `{a.get('component', 'Architecture')}`)")
            out.append(f"   - *Architectural Impact:* {a.get('impact', '')}")
        out.append("")

    if result.get("architectural_advisory_note"):
        out.extend(["## Architectural Advisory Note", result["architectural_advisory_note"], ""])

    if result.get("questions_for_team"):
        out.append("## Questions for the Engineering Team")
        out.extend(f"- {q}" for q in result["questions_for_team"])

    return "\n".join(out)
