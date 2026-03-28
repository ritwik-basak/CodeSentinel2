"""
orchestrator.py — Repo-level Orchestrator agent.

Makes a single Groq call to produce a high-level summary of the repository:
what it is, what it does, key technical areas, and structural concerns
visible from the file/import structure alone.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke

# README filenames we recognise (checked against the bare filename, not the path)
_README_NAMES = {"README.md", "readme.md", "README.rst", "README.txt", "README"}
_README_PREVIEW_CHARS = 3000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Orchestrator", run_type="chain")
def analyze(
    files: dict[str, str],
    parsed: dict[str, Any],
    language_breakdown: dict[str, int],
) -> dict[str, Any]:
    """
    Produce a structured repo summary using one LLM call.

    Parameters
    ----------
    files              : raw file contents from ``core.fetcher.fetch_repo_files``
    parsed             : per-file parse results from ``core.parser.parse_files``
    language_breakdown : language → file count from the fetcher

    Returns
    -------
    dict with keys: project_type, description, tech_areas, structural_concerns
    """
    readme        = _find_readme(files)
    all_imports   = _collect_imports(parsed)
    filenames     = sorted(files.keys())

    prompt = _build_prompt(language_breakdown, filenames, readme, all_imports)
    raw    = rate_limited_invoke(prompt)

    return _parse_response(raw)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(
    language_breakdown: dict[str, int],
    filenames: list[str],
    readme: str,
    all_imports: list[str],
) -> str:
    lang_lines = "\n".join(
        f"  {lang}: {count} files"
        for lang, count in sorted(language_breakdown.items(), key=lambda x: -x[1])
    )

    file_list = "\n".join(f"  {f}" for f in filenames[:60])
    imports_capped = all_imports[:40]
    import_list = ", ".join(imports_capped) if imports_capped else "(none detected)"

    return f"""You are a senior software engineer performing an initial triage of a GitHub repository.

Analyze the information below and respond with a structured JSON summary.

---
LANGUAGE BREAKDOWN:
{lang_lines}

FILES IN REPO ({len(filenames)} total):
{file_list}

README (up to {_README_PREVIEW_CHARS} characters):
{readme}

ALL IMPORTS FOUND ACROSS THE REPO:
{import_list}
---

Respond with ONLY a JSON object — no markdown, no explanation, no code fences — in this exact shape:

{{
  "project_type": "one-line label, e.g. Full-stack web application",
  "description": "2-4 sentence description of what this project does",
  "tech_areas": ["list", "of", "key", "technical", "areas"],
  "structural_concerns": ["list of concerns visible from structure alone, or empty list"]
}}

For tech_areas consider: REST API, GraphQL, database, authentication, data processing,
machine learning, LLM integration, React frontend, testing, websockets, caching, etc.
For structural_concerns consider: missing tests, God files, no documentation, circular
imports, mixed concerns, etc. Only report what is clearly visible from the file list and imports.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_readme(files: dict[str, str]) -> str:
    for path, content in files.items():
        if os.path.basename(path) in _README_NAMES:
            return content[:_README_PREVIEW_CHARS]
    return "(No README found in repository)"


def _collect_imports(parsed: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    for result in parsed.values():
        seen.update(result.get("imports", []))
    return sorted(seen)


def _parse_response(raw: str) -> dict[str, Any]:
    """
    Parse the LLM response into a dict.  Tries three strategies in order:
    1. Direct JSON parse of the stripped response.
    2. Extract a JSON block from a markdown code fence.
    3. Find the first {...} blob anywhere in the response.

    Falls back to a minimal error dict if all strategies fail.
    """
    text = raw.strip()

    # Strategy 1 — clean JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2 — fenced code block
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3 — first {...} blob
    blob_match = re.search(r"\{.*\}", text, re.DOTALL)
    if blob_match:
        try:
            return json.loads(blob_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback
    return {
        "project_type": "Unknown",
        "description": text[:300] if text else "No response from LLM.",
        "tech_areas": [],
        "structural_concerns": ["Could not parse structured response from LLM."],
    }
