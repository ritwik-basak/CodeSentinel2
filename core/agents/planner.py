"""
planner.py — Planner agent.

Receives the Orchestrator's repo summary plus parser statistics and decides
which specialist agents to activate, in what order, and with what specific
focus instructions.  Makes exactly ONE Groq call.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke

# ---------------------------------------------------------------------------
# Specialist agent catalogue (sent verbatim inside the prompt)
# ---------------------------------------------------------------------------

_AGENT_CATALOGUE = """1. bug_detector     — finds logic errors, null/undefined issues, async mistakes, unhandled edge cases
2. security_auditor — finds hardcoded secrets, SQL injection, unsafe input handling, exposed API keys
3. doc_checker      — checks missing docstrings, JSDoc, README quality, inline comment coverage
4. code_quality     — checks naming conventions, function complexity, code duplication, dead code"""

_ALL_AGENT_NAMES = {"bug_detector", "security_auditor", "doc_checker", "code_quality"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Planner", run_type="chain")
def plan(
    orchestrator_summary: dict[str, Any],
    language_breakdown: dict[str, int],
    total_functions: int,
    py_missing_doc: int,
    py_total_funcs: int,
    js_missing_doc: int,
    js_total_funcs: int,
) -> dict[str, Any]:
    """
    Decide which specialist agents to activate and how to focus them.

    Parameters
    ----------
    orchestrator_summary : output of ``core.agents.orchestrator.analyze``
    language_breakdown   : language → file count from the fetcher
    total_functions      : total function count across all parsed files
    py_missing_doc       : Python functions lacking docstrings
    py_total_funcs       : total Python functions
    js_missing_doc       : JS/TS functions lacking JSDoc
    js_total_funcs       : total JS/TS functions

    Returns
    -------
    dict with keys:
        reasoning, activated_agents, skipped_agents,
        priority_order, focus_areas
    """
    prompt = _build_prompt(
        orchestrator_summary,
        language_breakdown,
        total_functions,
        py_missing_doc, py_total_funcs,
        js_missing_doc, js_total_funcs,
    )
    raw = rate_limited_invoke(prompt)
    return _parse_response(raw)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(
    summary: dict[str, Any],
    language_breakdown: dict[str, int],
    total_functions: int,
    py_missing_doc: int,
    py_total_funcs: int,
    js_missing_doc: int,
    js_total_funcs: int,
) -> str:
    lang_lines = "\n".join(
        f"  {lang}: {count} files"
        for lang, count in sorted(language_breakdown.items(), key=lambda x: -x[1])
    )

    tech_areas_str       = ", ".join(summary.get("tech_areas", [])) or "none identified"
    concerns_str         = "\n".join(f"  - {c}" for c in summary.get("structural_concerns", [])) or "  (none)"
    py_doc_pct           = f"{py_missing_doc}/{py_total_funcs}" if py_total_funcs else "N/A"
    js_doc_pct           = f"{js_missing_doc}/{js_total_funcs}" if js_total_funcs else "N/A"

    return f"""You are the Planner for an AI-powered code review system.

Your job is to read the repository analysis below and decide which specialist
review agents to activate, in what priority order, and with what specific focus
instructions for each activated agent.

Think step by step and explain your reasoning before giving the final JSON answer.

---
REPOSITORY ANALYSIS (from Orchestrator):
  Project type : {summary.get('project_type', 'Unknown')}
  Description  : {summary.get('description', 'N/A')}
  Tech areas   : {tech_areas_str}
  Structural concerns:
{concerns_str}

LANGUAGE BREAKDOWN:
{lang_lines}

PARSER STATISTICS:
  Total functions     : {total_functions}
  Python missing docs : {py_doc_pct} functions
  JS/TS missing docs  : {js_doc_pct} functions

AVAILABLE SPECIALIST AGENTS:
{_AGENT_CATALOGUE}
---

Decide which agents to activate.  You may activate any subset — there is no
requirement to activate all of them.  Skipping an agent is valid if its focus
area is not relevant to this project.

Respond with ONLY a JSON object — no markdown, no code fences, no explanation
outside the JSON — in this exact shape:

{{
  "reasoning": "Your step-by-step explanation of each decision here",
  "activated_agents": ["list", "of", "agent", "names"],
  "skipped_agents": {{
    "agent_name": "one-line reason for skipping"
  }},
  "priority_order": ["agents in execution order, highest priority first"],
  "focus_areas": {{
    "agent_name": "specific instruction for this agent on what to focus on"
  }}
}}

Rules:
- Every activated agent must appear in both priority_order and focus_areas.
- Every agent not in activated_agents must appear in skipped_agents.
- Agent names must be exactly as listed in the catalogue.
- focus_areas instructions should be concrete and repo-specific, not generic.
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> dict[str, Any]:
    """
    Parse the LLM response using three fallback strategies, then validate
    and normalise the result.
    """
    text = raw.strip()

    parsed: dict | None = None

    # Strategy 1 — direct JSON parse
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2 — extract from markdown code fence
    if parsed is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            try:
                parsed = json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

    # Strategy 3 — first {...} blob in the response
    if parsed is None:
        blob = re.search(r"\{.*\}", text, re.DOTALL)
        if blob:
            try:
                parsed = json.loads(blob.group(0))
            except json.JSONDecodeError:
                pass

    if parsed is None:
        return _fallback(text)

    return _normalise(parsed)


def _normalise(data: dict) -> dict[str, Any]:
    """Ensure all expected keys exist with the right types."""
    activated = [
        a for a in data.get("activated_agents", [])
        if a in _ALL_AGENT_NAMES
    ]
    skipped = {
        k: v for k, v in data.get("skipped_agents", {}).items()
        if k in _ALL_AGENT_NAMES
    }
    # Any agent unaccounted for goes into skipped with a default reason
    for name in _ALL_AGENT_NAMES:
        if name not in activated and name not in skipped:
            skipped[name] = "Not mentioned in planner response."

    priority = [a for a in data.get("priority_order", []) if a in activated]
    # Append any activated agents missing from priority_order
    for a in activated:
        if a not in priority:
            priority.append(a)

    focus = {
        k: v for k, v in data.get("focus_areas", {}).items()
        if k in activated
    }

    return {
        "reasoning":        data.get("reasoning", ""),
        "activated_agents": activated,
        "skipped_agents":   skipped,
        "priority_order":   priority,
        "focus_areas":      focus,
    }


def _fallback(raw_text: str) -> dict[str, Any]:
    return {
        "reasoning":        raw_text[:500] if raw_text else "No response from LLM.",
        "activated_agents": list(_ALL_AGENT_NAMES),
        "skipped_agents":   {},
        "priority_order":   list(_ALL_AGENT_NAMES),
        "focus_areas":      {a: "General review" for a in _ALL_AGENT_NAMES},
    }
