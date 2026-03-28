"""
fixer.py — Self-debug loop agent.

Takes bugs found by bug_detector and attempts to fix them, then verifies
each fix using E2B sandboxed execution (Python/JS) or LLM reflection (JSX/TSX).

Execution modes
---------------
execute_python  — .py files:       E2B Python sandbox, up to 3 attempts
execute_js      — .js/.mjs files:  E2B Node subprocess wrapper, up to 3 attempts
reflect         — all other files: LLM validator loop, up to 3 attempts

If E2B_API_KEY is not set, all execute_* modes fall back to reflect automatically.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langsmith import traceable

from core.llm import rate_limited_invoke

_MAX_ATTEMPTS = 3

EXECUTABLE_LANGUAGES = {".py": "python", ".js": "javascript", ".mjs": "javascript"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@traceable(name="Fixer", run_type="chain")
def fix_bugs(bugs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Attempt to fix every bug that has both ``original_code`` and ``suggested_fix``.

    Parameters
    ----------
    bugs : list of bug dicts as returned by ``core.agents.bug_detector.detect``

    Returns
    -------
    List of fix-result dicts (one per fixable bug).
    """
    fixable = [b for b in bugs if b.get("original_code") and b.get("suggested_fix")]
    return [_fix_bug(bug) for bug in fixable]


# ---------------------------------------------------------------------------
# Per-bug dispatch
# ---------------------------------------------------------------------------

def _determine_mode(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if ext.lower() in EXECUTABLE_LANGUAGES:
        lang = EXECUTABLE_LANGUAGES[ext.lower()]
        return f"execute_{lang}"
    return "reflect"


def _fix_bug(bug: dict[str, Any]) -> dict[str, Any]:
    filename = bug.get("filename", "")
    mode     = _determine_mode(filename)

    # Fall back to reflect when the sandbox key is absent
    if mode.startswith("execute") and not os.environ.get("E2B_API_KEY"):
        print("    [warn] E2B_API_KEY not set — using reflect mode")
        mode = "reflect"

    result: dict[str, Any] = {
        "bug_title":     bug.get("title", ""),
        "filename":      filename,
        "function_name": bug.get("function_name", ""),
        "line":          bug.get("line"),
        "mode":          mode,
        "status":        "could_not_fix",
        "attempts":      0,
        "original_code": bug.get("original_code", ""),
        "fixed_code":    "",
        "verification":  "",
        "e2b_output":    "",
        "e2b_error":     "",
    }

    if mode.startswith("execute"):
        return _execute_loop(bug, mode, result)
    return _reflect_loop(bug, result)


# ---------------------------------------------------------------------------
# Execute mode — E2B sandbox loop
# ---------------------------------------------------------------------------

def _execute_loop(bug: dict, mode: str, result: dict) -> dict:
    language   = "python" if mode == "execute_python" else "javascript"
    prev_error: str | None = None
    fixed_code = ""

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result["attempts"] = attempt
        print(f"    Attempt {attempt}/{_MAX_ATTEMPTS}...")

        fixed_code = _generate_fix(bug, prev_error, fixed_code, attempt)
        stdout, error = _e2b_execute(fixed_code, language)

        result["fixed_code"]  = fixed_code
        result["e2b_output"]  = stdout
        result["e2b_error"]   = error or ""

        if error is None:
            result["status"]       = "fixed"
            result["verification"] = (
                f"E2B executed successfully on attempt {attempt}"
                + (f" | stdout: {stdout[:80]}" if stdout else "")
            )
            return result

        # Module not found means the sandbox can't run this code (e.g. React/frontend).
        # Fall back to LLM reflect mode immediately instead of wasting retries.
        if error and "ERR_MODULE_NOT_FOUND" in error:
            print(f"    [warn] Sandbox missing dependencies — falling back to reflect mode")
            result["mode"] = "reflect"
            result["e2b_error"] = ""
            return _reflect_loop(bug, result)

        prev_error = error

    return result


def _e2b_execute(code: str, language: str) -> tuple[str, str | None]:
    """
    Run code inside an E2B sandbox.

    Python → direct kernel execution.
    JavaScript → writes a temp .js file, executes via ``node`` subprocess
                 inside the Python kernel.

    Returns (stdout, error_string_or_None).
    """
    from e2b_code_interpreter import Sandbox

    sandbox = Sandbox(api_key=os.environ.get("E2B_API_KEY"))

    try:
        if language == "python":
            execution = sandbox.run_code(code)
        else:
            # Wrap JS in a Python subprocess call — works in the default Python sandbox
            js_runner = (
                "import subprocess, tempfile, os, sys\n"
                f"_code = {repr(code)}\n"
                "with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False) as _f:\n"
                "    _f.write(_code)\n"
                "    _fname = _f.name\n"
                "try:\n"
                "    _r = subprocess.run(\n"
                "        ['node', _fname], capture_output=True, text=True, timeout=10\n"
                "    )\n"
                "    sys.stdout.write(_r.stdout)\n"
                "    if _r.returncode != 0:\n"
                "        raise RuntimeError(_r.stderr.strip())\n"
                "finally:\n"
                "    os.unlink(_fname)\n"
            )
            execution = sandbox.run_code(js_runner)

        stdout = "\n".join(execution.logs.stdout) if execution.logs.stdout else ""
        error: str | None = None
        if execution.error:
            error = f"{execution.error.name}: {execution.error.value}"

        return stdout, error

    except Exception as exc:
        return "", str(exc)

    finally:
        sandbox.kill()


# ---------------------------------------------------------------------------
# Reflect mode — LLM validator loop
# ---------------------------------------------------------------------------

def _reflect_loop(bug: dict, result: dict) -> dict:
    prev_feedback: str | None = None
    fixed_code = ""

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result["attempts"] = attempt
        print(f"    Attempt {attempt}/{_MAX_ATTEMPTS}...")

        fixed_code = _generate_fix(bug, prev_feedback, fixed_code, attempt)
        result["fixed_code"] = fixed_code

        validation = _reflect_validate(bug, fixed_code)

        if validation.get("is_valid"):
            confidence = validation.get("confidence", 0.0)
            result["status"]       = "fixed"
            result["verification"] = (
                f"Validator approved with {confidence:.2f} confidence — "
                + validation.get("verdict", "")
            )
            return result

        issues = validation.get("issues", [])
        prev_feedback = validation.get("verdict", "Fix was not valid.") + (
            f" Issues: {', '.join(issues)}" if issues else ""
        )

    return result


def _reflect_validate(bug: dict, fixed_code: str) -> dict[str, Any]:
    prompt = f"""You are a code reviewer validating whether a proposed fix correctly solves a reported bug.

Original bug
  Title      : {bug.get('title', '')}
  Description: {bug.get('description', '')}

Original (buggy) code:
{bug.get('original_code', '')}

Proposed fix:
{fixed_code}

Does this fix correctly solve the bug?
Are there any new issues introduced by the fix?

Respond with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "is_valid": true,
  "confidence": 0.85,
  "issues": [],
  "verdict": "The fix correctly handles the edge case by adding a None check."
}}
"""
    raw = rate_limited_invoke(prompt)
    return _parse_validation(raw)


# ---------------------------------------------------------------------------
# Shared — fix generation
# ---------------------------------------------------------------------------

def _generate_fix(
    bug: dict,
    prev_problem: str | None,
    prev_code: str,
    attempt: int,
) -> str:
    if attempt == 1 or not prev_problem:
        prompt = f"""You are a code fixer. Fix this specific bug.

Bug: {bug.get('title', '')}
Description: {bug.get('description', '')}
File: {bug.get('filename', '')}
Function: {bug.get('function_name', 'N/A')} (line {bug.get('line', '?')})

Original code:
{bug.get('original_code', '')}

Suggested fix hint (may be incomplete — rewrite it properly):
{bug.get('suggested_fix', '')}

Write the complete fixed version of just this function.
The fix must be syntactically correct and executable.
Respond with ONLY the fixed code — no explanation, no markdown backticks.
"""
    else:
        prompt = f"""You are a code fixer. Your previous fix attempt failed. Rewrite it.

Bug: {bug.get('title', '')}
Description: {bug.get('description', '')}
File: {bug.get('filename', '')}
Function: {bug.get('function_name', 'N/A')} (line {bug.get('line', '?')})

Original code:
{bug.get('original_code', '')}

Previous fix (attempt {attempt - 1}):
{prev_code}

Problem with the previous attempt:
{prev_problem}

Write a corrected version that solves the original bug AND avoids the problem above.
Respond with ONLY the fixed code — no explanation, no markdown backticks.
"""
    return rate_limited_invoke(prompt).strip()


# ---------------------------------------------------------------------------
# Shared — JSON parsing
# ---------------------------------------------------------------------------

def _parse_validation(raw: str) -> dict[str, Any]:
    text    = raw.strip()
    default = {
        "is_valid":   False,
        "confidence": 0.0,
        "issues":     [],
        "verdict":    "Could not parse validation response.",
    }

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    blob = re.search(r"\{.*\}", text, re.DOTALL)
    if blob:
        try:
            return json.loads(blob.group(0))
        except json.JSONDecodeError:
            pass

    return default
