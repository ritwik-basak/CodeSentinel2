"""
code_quality.py — Code Quality agent.

Finds naming, complexity, and structural quality issues through two parallel tracks:

  Track A (Groq + Pinecone):
    1. Generate targeted search queries from the planner focus area  (1 Groq call)
    2. Search Pinecone, deduplicate, filter score > 0.45, rerank
    3. Analyze ALL unique remaining chunks for quality issues         (1 Groq call)

  Track B (pure Python, no LLM):
    4. Calculate approximate function lengths from parser line numbers
       → flag functions > 30 lines (warning) and > 50 lines (critical)
    5. Flag single-character function names outside the loop-variable allowlist

Track B findings are merged into the final issues list alongside Track A findings.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke
from core.vector_store import search
from core.reranker import rerank

_SCORE_THRESHOLD   = 0.45
_TOP_K_PER_QUERY   = 5
_LONG_FN_WARNING   = 30   # lines
_LONG_FN_CRITICAL  = 50   # lines
_LOOP_VAR_NAMES    = {"i", "j", "k", "n"}
_TOP_LONGEST       = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Code Quality", run_type="chain")
def analyze(focus_area: str, parsed: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    """
    Run the full code-quality pipeline.

    Parameters
    ----------
    focus_area : focus instruction from the planner
    parsed     : output of ``core.parser.parse_files``
    files      : raw file contents from ``core.fetcher.fetch_repo_files``

    Returns
    -------
    dict with keys:
        issues, overall_quality_score, summary, longest_functions
    """
    # ── Track A: Groq + Pinecone ───────────────────────────────────────────
    print("  Generating search queries...")
    queries = _generate_queries(focus_area)
    print(f"  Queries: {queries}")

    print("  Searching Pinecone...")
    raw_chunks = _search_and_deduplicate(queries)

    groq_issues: list[dict] = []
    groq_score  = 70
    groq_summary = ""

    if not raw_chunks:
        print("  No matching chunks found above threshold.")
    else:
        print(f"  Reranking {len(raw_chunks)} candidate chunks...")
        ranked = rerank(focus_area, raw_chunks)

        print(f"  Analyzing {len(ranked)} chunks for quality issues...")
        groq_result  = _analyze_for_quality(focus_area, ranked)
        groq_issues  = groq_result.get("issues", [])
        groq_score   = groq_result.get("overall_quality_score", 70)
        groq_summary = groq_result.get("summary", "")

    # ── Track B: Pure Python analysis ─────────────────────────────────────
    python_issues, longest_functions = _python_analysis(parsed, files)

    # ── Merge and return ───────────────────────────────────────────────────
    all_issues = groq_issues + python_issues

    return {
        "issues":               all_issues,
        "overall_quality_score": groq_score,
        "summary":              groq_summary,
        "longest_functions":    longest_functions[:_TOP_LONGEST],
    }


# ---------------------------------------------------------------------------
# Phase 1 — Query generation
# ---------------------------------------------------------------------------

def _generate_queries(focus_area: str) -> list[str]:
    prompt = f"""You are a code quality analysis assistant.

Given the following focus area for a code quality review, generate exactly 5 targeted
semantic search queries to find potentially problematic code.

Each query should target a specific quality issue such as:
  - functions that are too long or overly complex
  - duplicate or repeated code patterns
  - poor variable or function naming conventions
  - functions doing too many things (single responsibility violations)
  - deeply nested conditions or loops
  - magic numbers or hardcoded string values

Focus area: {focus_area}

Respond with ONLY a JSON array of 5 query strings — no explanation, no markdown:
["query 1", "query 2", "query 3", "query 4", "query 5"]
"""
    raw = rate_limited_invoke(prompt)
    return _parse_query_list(raw, fallback=focus_area)


def _parse_query_list(raw: str, fallback: str) -> list[str]:
    text = raw.strip()

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [q for q in result if isinstance(q, str)][:5]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return [q for q in result if isinstance(q, str)][:5]
        except json.JSONDecodeError:
            pass

    strings = re.findall(r'"([^"]{10,})"', text)
    if strings:
        return strings[:5]

    return [fallback]


# ---------------------------------------------------------------------------
# Phase 2 — Search, dedup, filter
# ---------------------------------------------------------------------------

def _search_and_deduplicate(queries: list[str]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    for query in queries:
        hits = search(query, top_k=_TOP_K_PER_QUERY, filter={"chunk_type": "function"})
        for hit in hits:
            if hit["chunk_id"] in seen_ids:
                continue
            if hit["score"] < _SCORE_THRESHOLD:
                continue
            seen_ids.add(hit["chunk_id"])
            results.append(hit)

    return results


# ---------------------------------------------------------------------------
# Phase 3 — Quality analysis (Groq)
# ---------------------------------------------------------------------------

def _analyze_for_quality(
    focus_area: str, chunks: list[dict[str, Any]]
) -> dict[str, Any]:
    chunks_text = _format_chunks(chunks)

    prompt = f"""You are a code quality reviewer.

Focus area: {focus_area}

Review the following code chunks for quality issues:
  - Functions that are too long (over 30 lines is a warning, over 50 is critical)
  - Poor naming (single-letter variables outside loops, ambiguous names)
  - Functions doing too many things (single responsibility violations)
  - Deeply nested conditions (3+ levels of indentation)
  - Hardcoded magic numbers or strings that should be constants
  - Obvious code duplication

Be specific. Only report real issues with exact locations.
Do NOT report style nitpicks that do not affect maintainability.

CODE CHUNKS:
{chunks_text}

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "issues": [
    {{
      "severity": "warning",
      "filename": "path/to/file.py",
      "function_name": "function_name",
      "line": 34,
      "issue_type": "too_long",
      "title": "short descriptive title",
      "description": "2-3 sentence explanation written for a developer who may be learning: what the problem is, why it makes the code harder to understand or maintain, and what concrete harm it could cause over time",
      "suggestion": "1-2 sentence actionable advice explaining what to do and why it will improve the code"
    }}
  ],
  "overall_quality_score": 65,
  "summary": "2-3 sentence overall assessment of code quality"
}}

issue_type must be one of:
  too_long | poor_naming | too_complex | duplication | magic_number | deep_nesting

If no real quality issues are found, return {{"issues": [], "overall_quality_score": 85, "summary": "Code quality is good."}}
"""
    raw = rate_limited_invoke(prompt)
    return _parse_quality_response(raw)


_MAX_CHUNK_CHARS = 600
_MAX_CHUNKS_FOR_PROMPT = 8

def _format_chunks(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for i, chunk in enumerate(chunks[:_MAX_CHUNKS_FOR_PROMPT], start=1):
        text = chunk["text"]
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS] + "\n... (truncated)"
        parts.append(f"[Chunk {i}]\n{text}")
    return "\n\n---\n\n".join(parts)


def _parse_quality_response(raw: str) -> dict[str, Any]:
    text = raw.strip()

    parsed: dict | None = None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    if parsed is None:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            try:
                parsed = json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

    if parsed is None:
        blob = re.search(r"\{.*\}", text, re.DOTALL)
        if blob:
            try:
                parsed = json.loads(blob.group(0))
            except json.JSONDecodeError:
                pass

    if parsed is None:
        return {"issues": [], "overall_quality_score": 0, "summary": ""}

    issues = [_normalise_issue(i) for i in parsed.get("issues", []) if isinstance(i, dict)]
    return {
        "issues":               issues,
        "overall_quality_score": parsed.get("overall_quality_score", 0),
        "summary":              parsed.get("summary", ""),
    }


def _normalise_issue(issue: dict) -> dict[str, Any]:
    return {
        "severity":      issue.get("severity", "warning"),
        "filename":      issue.get("filename", "unknown"),
        "function_name": issue.get("function_name") or issue.get("function", "unknown"),
        "line":          issue.get("line"),
        "issue_type":    issue.get("issue_type", "too_complex"),
        "title":         issue.get("title", "Unnamed issue"),
        "description":   issue.get("description", ""),
        "suggestion":    issue.get("suggestion", ""),
    }


# ---------------------------------------------------------------------------
# Phase 4 — Pure Python analysis (no LLM)
# ---------------------------------------------------------------------------

def _python_analysis(
    parsed: dict[str, Any],
    files:  dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns (issues, longest_functions) derived entirely from parser output
    and raw line counts — no Groq, no Pinecone.
    """
    issues: list[dict[str, Any]] = []
    all_lengths: list[dict[str, Any]] = []

    for filename, file_data in parsed.items():
        if not file_data.get("parsed"):
            continue

        functions = file_data.get("functions", [])
        if not functions:
            continue

        raw_content  = files.get(filename, "")
        total_lines  = raw_content.count("\n") + 1 if raw_content else 0

        sorted_funcs = sorted(functions, key=lambda f: f["line"])

        for idx, func in enumerate(sorted_funcs):
            name      = func["name"]
            start_line = func["line"]

            # Prefer exact end_line from tree-sitter; fall back to next-function heuristic
            end_line = func.get("end_line")
            if end_line:
                approx_length = max(end_line - start_line + 1, 1)
            elif idx + 1 < len(sorted_funcs):
                approx_length = sorted_funcs[idx + 1]["line"] - start_line
            else:
                approx_length = max(total_lines - start_line + 1, 1)

            all_lengths.append({
                "filename":      filename,
                "function_name": name,
                "line":          start_line,
                "approx_lines":  approx_length,
            })

            # Long function findings
            if approx_length > _LONG_FN_CRITICAL:
                issues.append({
                    "severity":      "critical",
                    "filename":      filename,
                    "function_name": name,
                    "line":          start_line,
                    "issue_type":    "too_long",
                    "title":         f"Function is {approx_length}+ lines long",
                    "description":   (
                        f"`{name}` is approximately {approx_length} lines long, which is well above the recommended maximum of {_LONG_FN_CRITICAL} lines. "
                        "Functions this large are very hard to read, test, and debug — when something goes wrong, it takes much longer to find the problem because there is so much code to look through. "
                        "They also tend to do many different things at once, which makes it risky to change one part without accidentally breaking another."
                    ),
                    "suggestion":    (
                        "Break this function into several smaller functions, each doing one specific job. "
                        "A good rule of thumb: if you can't describe what the function does in one sentence, it probably does too much."
                    ),
                })
            elif approx_length > _LONG_FN_WARNING:
                issues.append({
                    "severity":      "warning",
                    "filename":      filename,
                    "function_name": name,
                    "line":          start_line,
                    "issue_type":    "too_long",
                    "title":         f"Function is {approx_length}+ lines long",
                    "description":   (
                        f"`{name}` is approximately {approx_length} lines long, exceeding the recommended {_LONG_FN_WARNING}-line guideline. "
                        "Long functions are harder to read and understand at a glance, especially for developers who didn't write them. "
                        "They also become increasingly risky to modify, because a change in one part can unexpectedly affect something far below it in the same function."
                    ),
                    "suggestion":    (
                        "Look for logical groups of steps inside the function and extract each group into its own helper function with a clear name. "
                        "This makes each piece independently testable and much easier to reason about."
                    ),
                })

            # Single-character function name findings
            if len(name) == 1 and name not in _LOOP_VAR_NAMES:
                issues.append({
                    "severity":      "warning",
                    "filename":      filename,
                    "function_name": name,
                    "line":          start_line,
                    "issue_type":    "poor_naming",
                    "title":         f"Single-character function name `{name}`",
                    "description":   (
                        f"The function is named `{name}`, which is a single letter and gives no information about what it does. "
                        "When someone else reads this code — or when you come back to it after a few weeks — they will have no idea what `{name}` means without reading the entire function body. "
                        "Good function names act like short documentation: they tell you the purpose without requiring you to look inside."
                    ),
                    "suggestion":    (
                        "Rename the function to something descriptive that explains its purpose, like `calculate_total`, `validate_input`, or `fetch_user_data`. "
                        "If you can't think of a name, that's often a sign the function is doing too many things and should be split up."
                    ),
                })

    # Deduplicate: a function should appear at most once per issue_type
    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["filename"], issue["function_name"], issue["issue_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(issue)

    longest = sorted(all_lengths, key=lambda x: x["approx_lines"], reverse=True)
    return deduped, longest
