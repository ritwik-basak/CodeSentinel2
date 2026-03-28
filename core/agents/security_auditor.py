"""
security_auditor.py — Security Auditor agent.

Finds security vulnerabilities in the codebase through three phases:
  1. Generate targeted Pinecone search queries from the planner focus area (1 Groq call)
  2. Search Pinecone (5 focused queries + 1 broad secrets sweep), deduplicate,
     filter by score > 0.60, and rerank results
  3. Send ALL unique post-dedup chunks to Groq and return structured findings (1 Groq call)
"""

from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke
from core.vector_store import search
from core.reranker import rerank

_SCORE_THRESHOLD = 0.40   # lower than bug_detector — secrets can be subtly embedded
_TOP_K_PER_QUERY = 5
_SECRETS_SWEEP_QUERY = "hardcoded api key secret token password credential"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Security Auditor", run_type="chain")
def audit(focus_area: str) -> list[dict[str, Any]]:
    """
    Run the full security-audit pipeline for the given planner focus area.

    Parameters
    ----------
    focus_area : the focus instruction from the planner, e.g.
                 "focus on API key handling and external request validation"

    Returns
    -------
    List of vulnerability dicts, each with keys:
        severity, filename, function_name, line,
        title, description, vulnerable_code, secure_fix
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

    # ── Phase 3: Analyze ALL unique chunks (no fixed cap for security) ─────
    print(f"  Analyzing {len(ranked)} chunks for vulnerabilities...")
    return _analyze_for_vulnerabilities(focus_area, ranked)


# ---------------------------------------------------------------------------
# Phase 1 — Query generation
# ---------------------------------------------------------------------------

def _generate_queries(focus_area: str) -> list[str]:
    prompt = f"""You are a security code analysis assistant.

Given the following focus area for a security audit, generate exactly 5 targeted
semantic search queries to find potentially vulnerable code.

Each query should target a specific security risk such as:
  - hardcoded API keys, tokens, passwords, or secrets
  - exposed credentials in code
  - unsafe input handling or missing validation
  - SQL injection or NoSQL injection risks
  - insecure direct object references
  - sensitive data exposure
  - missing authentication or authorisation checks

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

    # Focused function-chunk searches for each generated query
    for query in queries:
        hits = search(query, top_k=_TOP_K_PER_QUERY, filter={"chunk_type": "function"})
        for hit in hits:
            if hit["chunk_id"] in seen_ids:
                continue
            if hit["score"] < _SCORE_THRESHOLD:
                continue
            seen_ids.add(hit["chunk_id"])
            results.append(hit)

    # Broad secrets sweep — no chunk_type filter so file/class chunks are included
    secrets_hits = search(_SECRETS_SWEEP_QUERY, top_k=_TOP_K_PER_QUERY, filter=None)
    for hit in secrets_hits:
        if hit["chunk_id"] in seen_ids:
            continue
        if hit["score"] < _SCORE_THRESHOLD:
            continue
        seen_ids.add(hit["chunk_id"])
        results.append(hit)

    return results


# ---------------------------------------------------------------------------
# Phase 3 — Vulnerability analysis
# ---------------------------------------------------------------------------

def _analyze_for_vulnerabilities(
    focus_area: str, chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chunks_text = _format_chunks(chunks)

    prompt = f"""You are a security auditor reviewing code for vulnerabilities.

Focus area: {focus_area}

Analyze the following code chunks and identify real security vulnerabilities.
Be specific about:
  - Exact location (filename, line number, function name)
  - Why it is a security risk
  - The specific vulnerable code
  - The secure fix

Do NOT report style preferences or non-security concerns.
Only report genuine security issues that could be exploited or cause data leakage.

CODE CHUNKS:
{chunks_text}

Severity guide:
  critical   — exposed secrets, auth bypass, injection vulnerabilities
  warning    — missing input validation, insecure practices that enable attack
  suggestion — security improvements that are best practice but not immediately exploitable

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "vulnerabilities": [
    {{
      "severity": "critical",
      "filename": "path/to/file.py",
      "function_name": "function_name",
      "line": 12,
      "title": "short descriptive title",
      "description": "2-4 sentence explanation written for a developer who may be unfamiliar with security: what the vulnerability is, why it is dangerous, and what a real attacker could do if they exploited it",
      "vulnerable_code": "the problematic code snippet (1-5 lines)",
      "secure_fix": "first explain in 1-2 plain-English sentences WHY the fix works and what concept it applies (e.g. parameterized queries, input validation, hashing), then show the corrected code snippet"
    }}
  ]
}}

If no real security vulnerabilities are found, return {{"vulnerabilities": []}}.
"""
    raw = rate_limited_invoke(prompt)
    return _parse_vulnerabilities(raw)


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


def _parse_vulnerabilities(raw: str) -> list[dict[str, Any]]:
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

    if parsed is None or "vulnerabilities" not in parsed:
        return []

    return [
        _normalise_vuln(v)
        for v in parsed["vulnerabilities"]
        if isinstance(v, dict)
    ]


def _normalise_vuln(vuln: dict) -> dict[str, Any]:
    """Ensure all expected keys exist, filling missing ones with safe defaults."""
    return {
        "severity":       vuln.get("severity", "warning"),
        "filename":       vuln.get("filename", "unknown"),
        "function_name":  vuln.get("function_name") or vuln.get("function", "unknown"),
        "line":           vuln.get("line"),
        "title":          vuln.get("title", "Unnamed vulnerability"),
        "description":    vuln.get("description", ""),
        "vulnerable_code": vuln.get("vulnerable_code", ""),
        "secure_fix":     vuln.get("secure_fix", ""),
    }
