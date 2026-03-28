from __future__ import annotations

import sys
import os

# Add project root to Python path so all core modules are findable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

"""
graph.py — LangGraph orchestration.

Wires all agents into a sequential StateGraph pipeline.
Each specialist agent node checks planner_result["activated_agents"] and
self-skips if not activated — no complex conditional routing needed.

Pipeline order
--------------
fetch → parse → embed → store → orchestrate → plan
→ bug_detect → fix → security → doc_check → quality → synthesize → END

Public surface
--------------
run_review_stream(review_id, repo_url)
    Generator that yields progress-event dicts as each node completes,
    plus one final {"type": "complete", "report": {...}} event at the end.
"""

import operator
import os
from datetime import datetime
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, StateGraph


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ReviewState(TypedDict):
    # Inputs
    repo_url:  str
    review_id: str

    # Pipeline data
    files:              dict
    parsed:             dict
    chunks:             list
    language_breakdown: dict
    total_functions:    int

    # Agent outputs
    orchestrator_result: dict
    planner_result:      dict
    bugs:                list
    vulnerabilities:     list
    doc_result:          dict
    quality_result:      dict
    fixes:               list

    # Final output
    report: dict

    # Progress — accumulates across nodes via operator.add
    progress:     Annotated[list, operator.add]
    current_step: str
    error:        Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat()


def _evt(step: str, status: str, message: str) -> dict:
    return {
        "type":      "progress",
        "step":      step,
        "status":    status,
        "message":   message,
        "timestamp": _now(),
    }


def _py_js_stats(parsed: dict) -> tuple[list, list, int, int]:
    """Returns (py_funcs, js_funcs, py_missing, js_missing)."""
    py_funcs = [
        f for r in parsed.values()
        if r.get("language") == "python" and r.get("parsed")
        for f in r.get("functions", [])
    ]
    js_funcs = [
        f for r in parsed.values()
        if r.get("language") in ("javascript", "typescript") and r.get("parsed")
        for f in r.get("functions", [])
    ]
    py_missing = sum(1 for f in py_funcs if not f.get("has_doc"))
    js_missing = sum(1 for f in js_funcs if not f.get("has_doc"))
    return py_funcs, js_funcs, py_missing, js_missing


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def fetch_node(state: ReviewState) -> dict[str, Any]:
    from core.fetcher import detect_primary_language, fetch_repo_files

    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo_url     = state["repo_url"]

    files, language_breakdown = fetch_repo_files(repo_url, github_token)
    primary   = detect_primary_language(language_breakdown)
    repo_name = repo_url.rstrip("/").split("/")[-1]

    return {
        "files":              files,
        "language_breakdown": language_breakdown,
        "current_step":       "fetch",
        "progress": [_evt("fetch", "complete",
            f"Fetched {len(files)} files from {repo_name} (primary: {primary})")],
    }


def parse_node(state: ReviewState) -> dict[str, Any]:
    from core.parser import parse_files

    parsed          = parse_files(state["files"])
    total_functions = sum(len(r.get("functions", [])) for r in parsed.values())

    return {
        "parsed":          parsed,
        "total_functions": total_functions,
        "current_step":    "parse",
        "progress": [_evt("parse", "complete",
            f"Parsed {len(parsed)} files, found {total_functions} functions")],
    }


def embed_node(state: ReviewState) -> dict[str, Any]:
    from core.embedder import embed_chunks

    chunks = embed_chunks(state["parsed"], state["files"])

    return {
        "chunks":       chunks,
        "current_step": "embed",
        "progress": [_evt("embed", "complete",
            f"Created {len(chunks)} embeddings")],
    }


def store_node(state: ReviewState) -> dict[str, Any]:
    from core.vector_store import upsert_chunks

    upsert_chunks(state["chunks"])

    return {
        "current_step": "store",
        "progress": [_evt("store", "complete",
            f"Stored {len(state['chunks'])} chunks in Pinecone")],
    }


def orchestrate_node(state: ReviewState) -> dict[str, Any]:
    from core.agents.orchestrator import analyze as orchestrate

    result    = orchestrate(state["files"], state["parsed"], state["language_breakdown"])
    proj_type = result.get("project_type", "Unknown")

    return {
        "orchestrator_result": result,
        "current_step":        "orchestrate",
        "progress": [_evt("orchestrate", "complete",
            f"Orchestrator identified project as: {proj_type}")],
    }


def plan_node(state: ReviewState) -> dict[str, Any]:
    from core.agents.planner import plan

    py_funcs, js_funcs, py_missing, js_missing = _py_js_stats(state["parsed"])

    result    = plan(
        orchestrator_summary = state["orchestrator_result"],
        language_breakdown   = state["language_breakdown"],
        total_functions      = state.get("total_functions", 0),
        py_missing_doc       = py_missing,
        py_total_funcs       = len(py_funcs),
        js_missing_doc       = js_missing,
        js_total_funcs       = len(js_funcs),
    )
    activated = result.get("activated_agents", [])

    return {
        "planner_result": result,
        "current_step":   "plan",
        "progress": [_evt("plan", "complete",
            f"Planner activated: {', '.join(activated) if activated else 'none'}")],
    }


def bug_detect_node(state: ReviewState) -> dict[str, Any]:
    activated = state["planner_result"].get("activated_agents", [])
    if "bug_detector" not in activated:
        return {
            "bugs":         [],
            "current_step": "bug_detect",
            "progress": [_evt("bug_detect", "skipped", "Bug Detector skipped by planner")],
        }

    from core.agents.bug_detector import detect as detect_bugs

    focus = state["planner_result"].get("focus_areas", {}).get(
        "bug_detector", "general bug detection"
    )
    bugs = detect_bugs(focus)

    return {
        "bugs":         bugs,
        "current_step": "bug_detect",
        "progress": [_evt("bug_detect", "complete",
            f"Bug Detector found {len(bugs)} bug(s)")],
    }


def fix_node(state: ReviewState) -> dict[str, Any]:
    bugs    = state.get("bugs", [])
    fixable = [b for b in bugs if b.get("original_code") and b.get("suggested_fix")]

    if not fixable:
        return {
            "fixes":        [],
            "current_step": "fix",
            "progress": [_evt("fix", "skipped", "No fixable bugs — Fixer skipped")],
        }

    from core.agents.fixer import fix_bugs

    fixes       = fix_bugs(bugs)
    fixed_count = sum(1 for f in fixes if f.get("status") == "fixed")

    return {
        "fixes":        fixes,
        "current_step": "fix",
        "progress": [_evt("fix", "complete",
            f"Fixer: {fixed_count}/{len(fixes)} bugs fixed automatically")],
    }


def security_node(state: ReviewState) -> dict[str, Any]:
    activated = state["planner_result"].get("activated_agents", [])
    if "security_auditor" not in activated:
        return {
            "vulnerabilities": [],
            "current_step":    "security",
            "progress": [_evt("security", "skipped", "Security Auditor skipped by planner")],
        }

    from core.agents.security_auditor import audit as audit_security

    focus = state["planner_result"].get("focus_areas", {}).get(
        "security_auditor", "general security audit"
    )
    vulns = audit_security(focus)

    return {
        "vulnerabilities": vulns,
        "current_step":    "security",
        "progress": [_evt("security", "complete",
            f"Security Auditor found {len(vulns)} vulnerability/vulnerabilities")],
    }


def doc_check_node(state: ReviewState) -> dict[str, Any]:
    activated = state["planner_result"].get("activated_agents", [])
    if "doc_checker" not in activated:
        return {
            "doc_result":   {},
            "current_step": "doc_check",
            "progress": [_evt("doc_check", "skipped", "Doc Checker skipped by planner")],
        }

    from core.agents.doc_checker import check as check_docs

    py_funcs, js_funcs, py_missing, js_missing = _py_js_stats(state["parsed"])

    result = check_docs(
        parsed         = state["parsed"],
        files          = state["files"],
        py_missing_doc = py_missing,
        py_total_funcs = len(py_funcs),
        js_missing_doc = js_missing,
        js_total_funcs = len(js_funcs),
    )
    score = result.get("documentation_score", 0)

    return {
        "doc_result":   result,
        "current_step": "doc_check",
        "progress": [_evt("doc_check", "complete",
            f"Doc Checker: documentation score {score}/100")],
    }


def quality_node(state: ReviewState) -> dict[str, Any]:
    activated = state["planner_result"].get("activated_agents", [])
    if "code_quality" not in activated:
        return {
            "quality_result": {},
            "current_step":   "quality",
            "progress": [_evt("quality", "skipped", "Code Quality skipped by planner")],
        }

    from core.agents.code_quality import analyze as analyze_quality

    focus  = state["planner_result"].get("focus_areas", {}).get(
        "code_quality", "general code quality"
    )
    result = analyze_quality(focus, state["parsed"], state["files"])
    score  = result.get("overall_quality_score", 0)

    return {
        "quality_result": result,
        "current_step":   "quality",
        "progress": [_evt("quality", "complete",
            f"Code Quality: score {score}/100")],
    }


def synthesize_node(state: ReviewState) -> dict[str, Any]:
    import json
    from core.agents.synthesizer import synthesize

    report = synthesize(
        repo_url           = state["repo_url"],
        files              = state["files"],
        language_breakdown = state["language_breakdown"],
        total_functions    = state.get("total_functions", 0),
        orchestrator       = state.get("orchestrator_result", {}),
        planner            = state.get("planner_result", {}),
        bugs               = state.get("bugs", []),
        vulnerabilities    = state.get("vulnerabilities", []),
        doc_findings       = state.get("doc_result", {}),
        quality_issues     = state.get("quality_result", {}),
        fixes              = state.get("fixes", []),
    )
    health = report.get("summary", {}).get("overall_health", "unknown")
    score  = report.get("summary", {}).get("health_score", 0)

    # Save report to review_output/ — works for both CLI and API paths
    try:
        out_dir  = os.path.join(project_root, "review_output")
        os.makedirs(out_dir, exist_ok=True)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"report_{ts}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Report saved → {out_path}")
    except Exception as exc:
        print(f"  [warn] Could not save report: {exc}")

    return {
        "report":       report,
        "current_step": "synthesize",
        "progress": [_evt("synthesize", "complete",
            f"Review complete — health: {health} ({score}/100)")],
    }


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------

_graph = StateGraph(ReviewState)

_graph.add_node("fetch",       fetch_node)
_graph.add_node("parse",       parse_node)
_graph.add_node("embed",       embed_node)
_graph.add_node("store",       store_node)
_graph.add_node("orchestrate", orchestrate_node)
_graph.add_node("plan",        plan_node)
_graph.add_node("bug_detect",  bug_detect_node)
_graph.add_node("fix",         fix_node)
_graph.add_node("security",    security_node)
_graph.add_node("doc_check",   doc_check_node)
_graph.add_node("quality",     quality_node)
_graph.add_node("synthesize",  synthesize_node)

_graph.set_entry_point("fetch")
_graph.add_edge("fetch",       "parse")
_graph.add_edge("parse",       "embed")
_graph.add_edge("embed",       "store")
_graph.add_edge("store",       "orchestrate")
_graph.add_edge("orchestrate", "plan")
_graph.add_edge("plan",        "bug_detect")
_graph.add_edge("bug_detect",  "fix")
_graph.add_edge("fix",         "security")
_graph.add_edge("security",    "doc_check")
_graph.add_edge("doc_check",   "quality")
_graph.add_edge("quality",     "synthesize")
_graph.add_edge("synthesize",  END)

app_graph = _graph.compile()


# ---------------------------------------------------------------------------
# Public runner — streaming generator
# ---------------------------------------------------------------------------

def run_review_stream(review_id: str, repo_url: str):
    """
    Generator.  Yields progress-event dicts as each node completes.
    The final yielded item has ``type="complete"`` and includes the full report.
    On any unhandled exception, yields ``type="error"`` and stops.
    """
    initial_state: ReviewState = {
        "repo_url":            repo_url,
        "review_id":           review_id,
        "files":               {},
        "parsed":              {},
        "chunks":              [],
        "language_breakdown":  {},
        "total_functions":     0,
        "orchestrator_result": {},
        "planner_result":      {},
        "bugs":                [],
        "vulnerabilities":     [],
        "doc_result":          {},
        "quality_result":      {},
        "fixes":               [],
        "report":              {},
        "progress":            [],
        "current_step":        "starting",
        "error":               None,
    }

    prev_len:    int               = 0
    final_state: ReviewState | None = None

    try:
        for state in app_graph.stream(
            initial_state,
            config={"run_name": f"codesentinel-{review_id}"},
            stream_mode="values",
        ):
            final_state = state
            progress    = state.get("progress", [])
            for event in progress[prev_len:]:
                yield event
            prev_len = len(progress)

    except Exception as exc:
        step = final_state.get("current_step", "unknown") if final_state else "unknown"
        yield {
            "type":      "error",
            "step":      step,
            "status":    "error",
            "message":   str(exc),
            "timestamp": _now(),
        }
        return

    report = (final_state or {}).get("report", {})
    yield {
        "type":      "complete",
        "step":      "done",
        "status":    "complete",
        "message":   "Review pipeline complete",
        "report":    report,
        "timestamp": _now(),
    }
