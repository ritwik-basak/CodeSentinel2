"""
doc_checker.py — Documentation Checker agent.

Assesses documentation quality across the codebase without touching Pinecone
or the reranker — all signal comes directly from parser output and the raw
README content.  Makes exactly 2 Groq calls:

  Call 1 — score + findings for undocumented functions
  Call 2 — README quality assessment (skipped when no README is present)
"""

from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke

_README_MAX_CHARS = 20000
_SAMPLE_JS_MAX   = 10
_UNDOC_THRESHOLD = 20   # above this we sample instead of sending everything


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Doc Checker", run_type="chain")
def check(
    parsed: dict[str, Any],
    files:  dict[str, str],
    py_missing_doc: int,
    py_total_funcs: int,
    js_missing_doc: int,
    js_total_funcs: int,
) -> dict[str, Any]:
    """
    Run the full documentation-check pipeline.

    Parameters
    ----------
    parsed          : output of ``core.parser.parse_files``
    files           : raw file contents from ``core.fetcher.fetch_repo_files``
    py_missing_doc  : Python functions lacking docstrings (pre-computed in main)
    py_total_funcs  : total Python functions parsed
    js_missing_doc  : JS/TS functions lacking JSDoc (pre-computed in main)
    js_total_funcs  : total JS/TS functions parsed

    Returns
    -------
    dict with keys:
        documentation_score, findings, summary, readme_assessment
    """
    # ── Step 1: Build undocumented-function inventory from parser output ───
    undocumented = _collect_undocumented(parsed)
    print(f"  Found {len(undocumented)} undocumented function(s) across repo")

    # ── Step 2: Sample if list is long ────────────────────────────────────
    sample = _smart_sample(undocumented)

    # ── Groq call 1: Function documentation findings ──────────────────────
    print(f"  Analyzing {len(sample)} function(s) for documentation findings...")
    findings_result = _call_function_doc_analysis(
        sample, py_missing_doc, py_total_funcs, js_missing_doc, js_total_funcs
    )

    # ── Groq call 2: README assessment (skipped if no README) ─────────────
    readme_content = _find_readme(files)
    if readme_content:
        print("  Assessing README quality...")
        readme_assessment = _call_readme_assessment(readme_content)
    else:
        print("  No README found — skipping README assessment.")
        readme_assessment = {
            "quality":          "missing",
            "word_count":       0,
            "has_description":  False,
            "has_setup":        False,
            "has_usage":        False,
            "has_api_docs":     False,
            "has_env_vars":     False,
            "has_contributing": False,
            "missing":          ["README file"],
        }

    # ── Blended documentation score ───────────────────────────────────────
    # 70% function docstring/JSDoc coverage + 30% README completeness
    total_functions = sum(
        len(file_data["functions"])
        for file_data in parsed.values()
        if file_data.get("parsed")
    )
    documented_count = total_functions - len(undocumented)
    fn_doc_score = round((documented_count / total_functions) * 100) if total_functions > 0 else 0

    _README_ITEMS = [
        "has_description", "has_setup", "has_usage",
        "has_api_docs", "has_env_vars", "has_contributing",
    ]
    readme_checked = sum(1 for k in _README_ITEMS if readme_assessment.get(k))
    readme_score   = round(readme_checked / len(_README_ITEMS) * 100)

    score = round(0.70 * fn_doc_score + 0.30 * readme_score)
    print(f"  Doc score: {score}/100 (fn={fn_doc_score}, readme={readme_score}, checked={readme_checked}/6)")

    return {
        "documentation_score": score,
        "fn_doc_score":        fn_doc_score,
        "readme_score":        readme_score,
        "readme_checked":      readme_checked,
        "documented_count":    documented_count,
        "total_functions":     total_functions,
        "undocumented_count":  len(undocumented),
        "findings":            findings_result.get("findings", []),
        "summary":             findings_result.get("summary", ""),
        "readme_assessment":   readme_assessment,
    }


# ---------------------------------------------------------------------------
# Step 1 — Collect undocumented functions from parser output
# ---------------------------------------------------------------------------

def _collect_undocumented(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    undocumented = []
    for filename, file_data in parsed.items():
        if not file_data.get("parsed"):
            continue
        lang = file_data.get("language", "")
        for func in file_data.get("functions", []):
            if not func.get("has_doc"):
                undocumented.append({
                    "filename":      filename,
                    "function_name": func["name"],
                    "line":          func["line"],
                    "language":      lang,
                })
    return undocumented


# ---------------------------------------------------------------------------
# Step 2 — Smart sampling when list exceeds threshold
# ---------------------------------------------------------------------------

def _smart_sample(undocumented: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(undocumented) <= _UNDOC_THRESHOLD:
        return undocumented

    py_funcs = [f for f in undocumented if f["language"] == "python"]
    js_funcs = [f for f in undocumented if f["language"] in ("javascript", "typescript")]

    # Longer function names generally signal more complex, higher-priority functions
    js_funcs.sort(key=lambda f: len(f["function_name"]), reverse=True)
    js_sample = js_funcs[:_SAMPLE_JS_MAX]

    return py_funcs + js_sample


# ---------------------------------------------------------------------------
# Groq call 1 — Function documentation findings
# ---------------------------------------------------------------------------

def _call_function_doc_analysis(
    undocumented: list[dict[str, Any]],
    py_missing: int,
    py_total:   int,
    js_missing: int,
    js_total:   int,
) -> dict[str, Any]:
    func_lines = "\n".join(
        f"  {f['filename']} :: {f['function_name']} (line {f['line']}, {f['language']})"
        for f in undocumented
    ) or "  (all functions are documented)"

    py_ratio = f"{py_missing}/{py_total}" if py_total else "N/A"
    js_ratio = f"{js_missing}/{js_total}" if js_total else "N/A"

    prompt = f"""You are a documentation quality reviewer for a software project.

The repository has the following undocumented functions:

{func_lines}

Overall statistics:
  Python functions missing docstrings : {py_ratio}
  JavaScript/TS functions missing JSDoc: {js_ratio}

Generate a documentation quality report.

Group findings by severity:
  critical   — core business logic or public-facing functions with no documentation
  warning    — utility or helper functions with no documentation
  suggestion — simple, short, or private functions that would still benefit from docs

Also provide an overall documentation score out of 100 (100 = fully documented).

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "documentation_score": 45,
  "findings": [
    {{
      "severity": "critical",
      "filename": "path/to/file.py",
      "function_name": "function_name",
      "line": 34,
      "title": "Missing docstring on core function",
      "description": "What this function appears to do and why documentation is important here",
      "suggested_doc": "One-sentence description of what this function should document."
    }}
  ],
  "summary": "2-3 sentence overall assessment of the project's documentation health"
}}
"""
    raw = rate_limited_invoke(prompt)
    return _parse_json_response(raw, fallback_key="findings")


# ---------------------------------------------------------------------------
# Groq call 2 — README assessment
# ---------------------------------------------------------------------------

def _call_readme_assessment(readme_content: str) -> dict[str, Any]:
    prompt = f"""You are a documentation reviewer. Read the README below carefully and answer each question honestly based on what is actually present.

README:
{readme_content}

Answer each question by reading the actual README content above. Do NOT default to false — only mark something false if the content is genuinely absent.

Detection rules (be generous — partial coverage counts as true):
- has_description: true if there is any introductory paragraph, tagline, or section describing what the project does
- has_setup: true if there is ANY section covering installation, setup, prerequisites, "getting started", "how to run", pip install, npm install, venv, etc. — even partial steps count
- has_usage: true if there are usage instructions, example commands, screenshots, or a "how to use" section
- has_api_docs: true if there is an API endpoints table, route list, swagger mention, or any documentation of HTTP endpoints
- has_env_vars: true if there is a .env section, environment variables table, or list of required API keys / config variables
- has_contributing: true if there is a contributing guide, PR process, or coding standards section
- quality: "good" if 5-6 items are present, "basic" if 3-4 are present, "poor" if 0-2 are present
- missing: list only items that are genuinely absent

Respond with ONLY a JSON object — no markdown, no text outside the JSON:
{{
  "readme_assessment": {{
    "quality": "<poor|basic|good>",
    "word_count": <approximate word count as integer>,
    "has_description": <true|false>,
    "has_setup": <true|false>,
    "has_usage": <true|false>,
    "has_api_docs": <true|false>,
    "has_env_vars": <true|false>,
    "has_contributing": <true|false>,
    "missing": ["<only items that are genuinely absent>"]
  }}
}}
"""
    raw = rate_limited_invoke(prompt)
    parsed = _parse_json_response(raw, fallback_key="readme_assessment")
    return parsed.get("readme_assessment", {
        "quality":          "poor",
        "word_count":       0,
        "has_description":  False,
        "has_setup":        False,
        "has_usage":        False,
        "has_api_docs":     False,
        "has_env_vars":     False,
        "has_contributing": False,
        "missing":          ["Could not parse README assessment"],
    })


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _find_readme(files: dict[str, str]) -> str:
    content = files.get("__readme__", "")
    return content[:_README_MAX_CHARS]


def _parse_json_response(raw: str, fallback_key: str) -> dict[str, Any]:
    text = raw.strip()

    # Strategy 1 — direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2 — extract from markdown code fence
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3 — first {...} blob
    blob = re.search(r"\{.*\}", text, re.DOTALL)
    if blob:
        try:
            return json.loads(blob.group(0))
        except json.JSONDecodeError:
            pass

    return {fallback_key: [], "summary": "Could not parse LLM response.", "documentation_score": 0}
