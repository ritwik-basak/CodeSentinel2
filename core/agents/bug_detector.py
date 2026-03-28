"""
bug_detector.py — Bug Detector agent.

Finds real bugs in the codebase through three phases:
  1. Generate targeted Pinecone search queries from the planner focus area (1 Groq call)
  2. Search Pinecone, deduplicate, filter, and rerank results
  3. Analyze the top chunks and return structured bug findings (1 Groq call)
"""

from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke
from core.vector_store import search
from core.reranker import rerank

_SCORE_THRESHOLD = 0.45
_TOP_K_PER_QUERY = 5
_TOP_CHUNKS_FOR_ANALYSIS = 10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Bug Detector", run_type="chain")
def detect(focus_area: str) -> list[dict[str, Any]]:
    """
    Run the full bug-detection pipeline for the given planner focus area.

    Parameters
    ----------
    focus_area : the focus instruction from the planner, e.g.
                 "focus on async functions and API call error handling"

    Returns
    -------
    List of bug dicts, each with keys:
        severity, filename, function_name, line,
        title, description, original_code, suggested_fix
    """
    # ── Phase 1: Generate targeted search queries ──────────────────────────
    print("  Generating search queries...")
    queries = _generate_queries(focus_area)
    print(f"  Queries: {queries}")

    # ── Phase 2: Search, deduplicate, filter, rerank ───────────────────────
    print("  Searching Pinecone...")
    raw_chunks = _search_and_deduplicate(queries)

    if not raw_chunks:
        print("  No matching chunks found above threshold.")
        return []

    print(f"  Reranking {len(raw_chunks)} candidate chunks...")
    ranked = rerank(focus_area, raw_chunks)
    top_chunks = ranked[:_TOP_CHUNKS_FOR_ANALYSIS]

    # ── Phase 3: Analyze top chunks for bugs ──────────────────────────────
    print(f"  Analyzing top {len(top_chunks)} chunks for bugs...")
    return _analyze_for_bugs(focus_area, top_chunks)


# ---------------------------------------------------------------------------
# Phase 1 — Query generation
# ---------------------------------------------------------------------------

def _generate_queries(focus_area: str) -> list[str]:
    prompt = f"""You are a code analysis assistant helping to find bugs in a codebase.

Given the following focus area for bug detection, generate exactly 5 targeted
semantic search queries. Each query should target a specific type of bug or
risky pattern that is likely to appear in code matching the focus area.

Focus area: {focus_area}

Respond with ONLY a JSON array of 5 query strings — no explanation, no markdown:
["query 1", "query 2", "query 3", "query 4", "query 5"]
"""
    raw = rate_limited_invoke(prompt)
    return _parse_query_list(raw, fallback=focus_area)


def _parse_query_list(raw: str, fallback: str) -> list[str]:
    text = raw.strip()

    # Strategy 1 — direct array parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [q for q in result if isinstance(q, str)][:5]
    except json.JSONDecodeError:
        pass

    # Strategy 2 — array inside markdown fence or prose
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return [q for q in result if isinstance(q, str)][:5]
        except json.JSONDecodeError:
            pass

    # Strategy 3 — extract all quoted strings
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
# Phase 3 — Bug analysis
# ---------------------------------------------------------------------------

def _analyze_for_bugs(
    focus_area: str, chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunks_text = _format_chunks(chunks)

    prompt = f"""You are a senior software engineer performing a code bug review.

Focus area: {focus_area}

Analyze the following code chunks carefully and identify real bugs — logic errors,
missing error handling, null/undefined risks, unhandled edge cases, async mistakes,
off-by-one errors, or incorrect assumptions. Do NOT report style preferences or
minor nitpicks — only report genuine issues that could cause incorrect behavior,
crashes, or security problems.

Be specific: reference the exact filename, function name, and line number.
For each bug provide the problematic code and a corrected version.

CODE CHUNKS:
{chunks_text}

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "bugs": [
    {{
      "severity": "critical",
      "filename": "path/to/file.py",
      "function_name": "function_name",
      "line": 34,
      "title": "short descriptive title",
      "description": "2-4 sentence explanation written for a developer who may be new to this area: what the bug is, why the current code is wrong, and what will actually happen at runtime if this bug is triggered (e.g. crash, wrong value returned, infinite loop)",
      "original_code": "the problematic code snippet (1-5 lines)",
      "suggested_fix": "the corrected version of the same snippet"
    }}
  ]
}}

Severity levels:
  critical   — could cause crashes, data loss, or security vulnerabilities
  warning    — incorrect behavior in edge cases or likely runtime errors
  suggestion — code that works but is fragile or likely to break under change

If no real bugs are found, return {{"bugs": []}}.
"""
    raw = rate_limited_invoke(prompt)
    return _parse_bugs(raw)


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


def _parse_bugs(raw: str) -> list[dict[str, Any]]:
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

    # Strategy 3 — first {...} blob
    if parsed is None:
        blob = re.search(r"\{.*\}", text, re.DOTALL)
        if blob:
            try:
                parsed = json.loads(blob.group(0))
            except json.JSONDecodeError:
                pass

    if parsed is None or "bugs" not in parsed:
        return []

    return [_normalise_bug(b) for b in parsed["bugs"] if isinstance(b, dict)]


def _normalise_bug(bug: dict) -> dict[str, Any]:
    """Ensure all expected keys exist, filling missing ones with safe defaults."""
    return {
        "severity":      bug.get("severity", "warning"),
        "filename":      bug.get("filename", "unknown"),
        "function_name": bug.get("function_name") or bug.get("function", "unknown"),
        "line":          bug.get("line"),
        "title":         bug.get("title", "Unnamed issue"),
        "description":   bug.get("description", ""),
        "original_code": bug.get("original_code", ""),
        "suggested_fix": bug.get("suggested_fix", ""),
    }
