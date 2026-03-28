"""
synthesizer.py — Final report synthesis agent.

Takes all outputs from every agent and produces one unified structured
code review report.  Makes exactly ONE Groq call to generate an executive
summary; the rest of the report is assembled in Python.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Synthesizer", run_type="chain")
def synthesize(
    repo_url:           str,
    files:              dict[str, str],
    language_breakdown: dict[str, int],
    total_functions:    int,
    orchestrator:       dict[str, Any],
    planner:            dict[str, Any],
    bugs:               list[dict[str, Any]],
    vulnerabilities:    list[dict[str, Any]],
    doc_findings:       dict[str, Any],
    quality_issues:     dict[str, Any],
    fixes:              list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Synthesize all agent outputs into one complete review report.

    Returns the complete_report dict.
    """
    # ── Normalize inputs that may arrive as raw strings ────────────────────
    if isinstance(orchestrator, str):
        try:
            orchestrator = json.loads(orchestrator)
        except Exception:
            orchestrator = {
                "project_type":       "Unknown",
                "description":        orchestrator,
                "tech_areas":         [],
                "structural_concerns": [],
            }

    if isinstance(planner, str):
        try:
            planner = json.loads(planner)
        except Exception:
            planner = {
                "activated_agents": [],
                "reasoning":        planner,
            }

    # ── Compute counts for the prompt ─────────────────────────────────────
    bug_counts    = _severity_counts(bugs)
    vuln_counts   = _severity_counts(vulnerabilities)
    doc_score     = doc_findings.get("documentation_score", 0)
    quality_score = quality_issues.get("overall_quality_score", 0)
    fixed_count   = sum(1 for f in fixes if f.get("status") == "fixed")

    activated = planner.get("activated_agents", [])

    # ── Build top-critical list for the prompt ─────────────────────────────
    critical_items = _top_critical(bugs, vulnerabilities)

    # ── Single Groq call ──────────────────────────────────────────────────
    print("  Calling Groq for executive summary...")
    summary = _call_groq(
        orchestrator    = orchestrator,
        activated       = activated,
        bugs            = bugs,
        bug_counts      = bug_counts,
        vulnerabilities = vulnerabilities,
        vuln_counts     = vuln_counts,
        doc_score       = doc_score,
        quality_score   = quality_score,
        fixed_count     = fixed_count,
        critical_items  = critical_items,
    )

    # ── Assemble complete report in Python ─────────────────────────────────
    complete_report: dict[str, Any] = {
        "metadata": {
            "repo_url":         repo_url,
            "timestamp":        datetime.now().isoformat(),
            "total_files":      len(files),
            "total_functions":  total_functions,
            "languages":        language_breakdown,
            "project_type":     orchestrator.get("project_type", ""),
            "project_description": orchestrator.get("description", ""),
        },
        "summary":          summary,
        "agents_activated": activated,
        "bugs":             bugs,
        "vulnerabilities":  vulnerabilities,
        "doc_report": {
            "score":              doc_score,
            "fn_doc_score":       doc_findings.get("fn_doc_score"),
            "readme_score":       doc_findings.get("readme_score"),
            "readme_checked":     doc_findings.get("readme_checked"),
            "documented_count":   doc_findings.get("documented_count"),
            "total_functions":    doc_findings.get("total_functions"),
            "undocumented_count": doc_findings.get("undocumented_count"),
            "readme_quality":     doc_findings.get("readme_assessment", {}).get("quality", "unknown"),
            "readme_assessment":  doc_findings.get("readme_assessment", {}),
            "findings":           doc_findings.get("findings", []),
        },
        "quality_report": {
            "score":             quality_score,
            "summary":           quality_issues.get("summary", ""),
            "longest_functions": quality_issues.get("longest_functions", []),
            "issues":            quality_issues.get("issues", []),
        },
        "fixes": fixes,
    }

    return complete_report


# ---------------------------------------------------------------------------
# Groq call
# ---------------------------------------------------------------------------

def _call_groq(
    orchestrator:    dict[str, Any],
    activated:       list[str],
    bugs:            list[dict[str, Any]],
    bug_counts:      dict[str, int],
    vulnerabilities: list[dict[str, Any]],
    vuln_counts:     dict[str, int],
    doc_score:       int,
    quality_score:   int,
    fixed_count:     int,
    critical_items:  list[str],
) -> dict[str, Any]:
    project_type   = orchestrator.get("project_type", "Unknown")
    description    = orchestrator.get("description", "")
    critical_block = "\n".join(f"  - {item}" for item in critical_items) or "  (none)"

    prompt = f"""You are a senior code reviewer. You have received analysis from multiple specialist agents.
Produce a concise executive summary of the overall code review.

Project: {project_type} — {description}

Agents activated: {', '.join(activated) if activated else 'none'}

Findings summary:
- Bugs found: {len(bugs)} ({bug_counts['critical']} critical, {bug_counts['warning']} warning, {bug_counts['suggestion']} suggestion)
- Vulnerabilities: {len(vulnerabilities)} ({vuln_counts['critical']} critical, {vuln_counts['warning']} warning)
- Documentation score: {doc_score}/100
- Code quality score: {quality_score}/100
- Bugs fixed automatically: {fixed_count}/{len(bugs)}

Top critical findings:
{critical_block}

Scoring guide — use the actual findings above to determine the score:
- Start from the average of documentation score ({doc_score}) and code quality score ({quality_score})
- Deduct 5-10 pts per critical bug (found {bug_counts['critical']})
- Deduct 3-5 pts per critical vulnerability (found {vuln_counts['critical']})
- Add up to 10 pts if most bugs were auto-fixed ({fixed_count}/{len(bugs)} fixed)
- Round to the nearest integer. Do NOT default to 65.

overall_health guide:
- 80-100 → "excellent"
- 65-79  → "good"
- 40-64  → "fair"
- 0-39   → "poor"

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "overall_health": "<poor|fair|good|excellent based on score>",
  "health_score": <integer 0-100 computed from the guide above>,
  "executive_summary": "<3-4 sentence overview of the codebase health>",
  "top_priorities": [
    "<First thing the developer should fix>",
    "<Second priority>",
    "<Third priority>"
  ],
  "strengths": [
    "<What the codebase does well>"
  ],
  "verdict": "<One punchy sentence overall verdict>"
}}

top_priorities must have exactly 3 items.
"""
    raw = rate_limited_invoke(prompt)
    return _parse_summary(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _severity_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "warning": 0, "suggestion": 0}
    for item in items:
        sev = item.get("severity", "warning").lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def _top_critical(
    bugs:            list[dict[str, Any]],
    vulnerabilities: list[dict[str, Any]],
) -> list[str]:
    """Return up to 3 highest-severity items formatted as strings."""
    _ORDER = {"critical": 0, "warning": 1, "suggestion": 2}
    candidates: list[tuple[int, str]] = []

    for b in bugs:
        sev   = b.get("severity", "warning").lower()
        label = (
            f"[BUG/{sev.upper()}] {b.get('title', '')} "
            f"— {b.get('filename', '')} :: {b.get('function_name', '')}: "
            f"{b.get('description', '')[:120]}"
        )
        candidates.append((_ORDER.get(sev, 2), label))

    for v in vulnerabilities:
        sev   = v.get("severity", "warning").lower()
        label = (
            f"[VULN/{sev.upper()}] {v.get('title', '')} "
            f"— {v.get('filename', '')} :: {v.get('function_name', '')}: "
            f"{v.get('description', '')[:120]}"
        )
        candidates.append((_ORDER.get(sev, 2), label))

    candidates.sort(key=lambda x: x[0])
    return [label for _, label in candidates[:3]]


def _parse_summary(raw: str) -> dict[str, Any]:
    text = raw.strip()
    default: dict[str, Any] = {
        "overall_health":    "fair",
        "health_score":      50,
        "executive_summary": "Could not parse executive summary.",
        "top_priorities":    [],
        "strengths":         [],
        "verdict":           "",
    }

    result = None
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        pass

    if result is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            try:
                result = json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

    if result is None:
        blob = re.search(r"\{.*\}", text, re.DOTALL)
        if blob:
            try:
                result = json.loads(blob.group(0))
            except json.JSONDecodeError:
                pass

    if result is None:
        return default

    # Ensure health_score is a real integer in range
    score = result.get("health_score", 50)
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = 50
    result["health_score"] = score

    # Ensure overall_health is consistent with the score
    if score >= 80:
        result["overall_health"] = "excellent"
    elif score >= 65:
        result["overall_health"] = "good"
    elif score >= 40:
        result["overall_health"] = "fair"
    else:
        result["overall_health"] = "poor"

    return result
