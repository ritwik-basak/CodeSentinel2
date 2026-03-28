import json
import os
from datetime import datetime
from dotenv import load_dotenv
from core.fetcher import fetch_repo_files, detect_primary_language
from core.parser import parse_files
from core.embedder import embed_chunks
from core.vector_store import upsert_chunks, search
from core.agents.orchestrator import analyze as orchestrate
from core.agents.planner import plan
from core.agents.bug_detector import detect as detect_bugs
from core.agents.security_auditor import audit as audit_security
from core.agents.doc_checker import check as check_docs
from core.agents.code_quality import analyze as analyze_quality
from core.agents.fixer import fix_bugs
from core.agents.synthesizer import synthesize

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
GITHUB_REPO_URL = "https://github.com/ritwik-basak/rag-pdf-chatbot"  # swap this out to test

# ── Run ───────────────────────────────────────────────────────────────────────
def main():
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise EnvironmentError(
            "GITHUB_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    print(f"\nFetching repository: {GITHUB_REPO_URL}")
    print("─" * 60)

    files, language_breakdown = fetch_repo_files(GITHUB_REPO_URL, github_token)

    total = len(files)
    primary = detect_primary_language(language_breakdown)

    print(f"\nFiles fetched:       {total}")
    print(f"Primary language:    {primary}")

    print("\nLanguage breakdown:")
    for lang, count in sorted(language_breakdown.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"  {lang:<14} {count:>4}  {bar}")

    print("\nFirst 5 files fetched:")
    for i, filename in enumerate(list(files.keys())[:5], start=1):
        print(f"  {i}. {filename}")

    # ── Parse ─────────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("Parsing files...")

    parsed = parse_files(files)

    # Aggregate stats
    total_funcs = sum(len(r["functions"]) for r in parsed.values())

    py_funcs = [
        f for r in parsed.values()
        if r["language"] == "python" and r["parsed"]
        for f in r["functions"]
    ]
    js_funcs = [
        f for r in parsed.values()
        if r["language"] in ("javascript", "typescript") and r["parsed"]
        for f in r["functions"]
    ]

    py_missing = sum(1 for f in py_funcs if not f["has_doc"])
    js_missing = sum(1 for f in js_funcs if not f["has_doc"])

    print(f"\nTotal functions found:               {total_funcs}")
    print(f"Python functions missing docstrings: {py_missing}/{len(py_funcs)}")
    print(f"JavaScript functions missing JSDoc:  {js_missing}/{len(js_funcs)}")

    # ── First Python file ──────────────────────────────────────────────────────
    first_py = next(
        (
            (fp, r) for fp, r in parsed.items()
            if r["language"] == "python" and r["parsed"] and r["functions"]
        ),
        None,
    )
    if first_py:
        fp, result = first_py
        print(f"\n── First Python file: {fp}")
        print(json.dumps(result, indent=2))

    # ── First JavaScript / TypeScript file ────────────────────────────────────
    first_js = next(
        (
            (fp, r) for fp, r in parsed.items()
            if r["language"] in ("javascript", "typescript") and r["parsed"] and r["functions"]
        ),
        None,
    )
    if first_js:
        fp, result = first_js
        print(f"\n── First JavaScript/TS file: {fp}")
        print(json.dumps(result, indent=2))

    # ── Embed ──────────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    chunks = embed_chunks(parsed, files)

    type_counts: dict[str, int] = {}
    for c in chunks:
        type_counts[c["chunk_type"]] = type_counts.get(c["chunk_type"], 0) + 1

    print(f"\nTotal chunks created: {len(chunks)}")
    print(f"  Function chunks:     {type_counts.get('function', 0)}")
    print(f"  Class chunks:        {type_counts.get('class', 0)}")
    print(f"  File summary chunks: {type_counts.get('file', 0)}")

    if chunks:
        print(f"\nEmbedding shape: ({len(chunks[0]['embedding'])},)")

        func_chunk  = next((c for c in chunks if c["chunk_type"] == "function"), None)
        class_chunk = next((c for c in chunks if c["chunk_type"] == "class"), None)
        file_chunk  = next((c for c in chunks if c["chunk_type"] == "file"), None)

        if func_chunk:
            print(f"\n── Sample function chunk  [{func_chunk['filename']}]")
            print(func_chunk["text"])

        if class_chunk:
            print(f"\n── Sample class chunk  [{class_chunk['filename']}]")
            print(class_chunk["text"])

        if file_chunk:
            print(f"\n── Sample file summary chunk  [{file_chunk['filename']}]")
            print(file_chunk["text"])

    # ── Store in Pinecone ──────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    upsert_chunks(chunks)

    # ── Test searches ──────────────────────────────────────────────────────────
    test_queries = [
        "functions that handle API calls",
        "functions missing error handling",
        "functions that process stock data",
    ]
    func_filter = {"chunk_type": "function"}

    for query in test_queries:
        print(f"\nSearch: \"{query}\"")
        results = search(query, top_k=3, filter=func_filter)
        if not results:
            print("  (no results)")
            continue
        for r in results:
            preview = r["text"][:100].replace("\n", " ")
            print(f"  [{r['score']:.3f}] {r['filename']} :: {r['function_name']} (line {r['line']})")
            print(f"          {preview}...")

    # ── Orchestrator ───────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("🔍 Orchestrator analyzing repo...")
    summary = orchestrate(files, parsed, language_breakdown)

    print(f"\nProject type:  {summary.get('project_type', 'N/A')}")
    print(f"\nDescription:\n  {summary.get('description', 'N/A')}")

    tech_areas = summary.get("tech_areas", [])
    if tech_areas:
        print("\nKey technical areas:")
        for area in tech_areas:
            print(f"  • {area}")

    concerns = summary.get("structural_concerns", [])
    if concerns:
        print("\nStructural concerns:")
        for concern in concerns:
            print(f"  ⚠  {concern}")
    else:
        print("\nStructural concerns: none detected")

    # ── Planner ────────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("🧠 Planner deciding which agents to activate...")

    plan_result = plan(
        orchestrator_summary=summary,
        language_breakdown=language_breakdown,
        total_functions=total_funcs,
        py_missing_doc=py_missing,
        py_total_funcs=len(py_funcs),
        js_missing_doc=js_missing,
        js_total_funcs=len(js_funcs),
    )

    print(f"\nReasoning:\n  {plan_result['reasoning']}")

    print("\nAgent activation decisions:")
    for agent in plan_result["activated_agents"]:
        print(f"  ✅ {agent}")
    for agent, reason in plan_result["skipped_agents"].items():
        print(f"  ❌ {agent}  —  {reason}")

    print(f"\nExecution order:")
    for i, agent in enumerate(plan_result["priority_order"], start=1):
        print(f"  {i}. {agent}")

    print("\nFocus areas:")
    for agent, focus in plan_result["focus_areas"].items():
        print(f"  [{agent}]  {focus}")

    # ── Bug Detector ───────────────────────────────────────────────────────────
    bugs: list[dict] = []
    if "bug_detector" in plan_result["activated_agents"]:
        print("\n" + "─" * 60)
        print("🐛 Bug Detector running...")
        focus = plan_result["focus_areas"].get("bug_detector", "general bug detection")

        bugs = detect_bugs(focus)

        _SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}
        for bug in bugs:
            sev  = bug["severity"].lower()
            icon = _SEVERITY_ICON.get(sev, "⚪")
            print(f"\n  {icon} [{sev.upper()}] {bug['title']}")
            print(f"     File: {bug['filename']} :: {bug['function_name']}"
                  + (f" (line {bug['line']})" if bug["line"] else ""))
            print(f"     {bug['description']}")
            if bug["original_code"]:
                print(f"     Original : {bug['original_code'][:120]}")
            if bug["suggested_fix"]:
                print(f"     Fix      : {bug['suggested_fix'][:120]}")

        print(f"\n  Found {len(bugs)} bug(s)")

    # ── Fixer ──────────────────────────────────────────────────────────────────
    fix_results: list[dict] = []
    if bugs:
        print("\n" + "─" * 60)
        print("🔧 Fixer Agent running...")
        fixable = [b for b in bugs if b.get("original_code") and b.get("suggested_fix")]
        print(f"Processing {len(fixable)} bug(s) from Bug Detector...")

        fix_results = fix_bugs(bugs)

        _MODE_LABEL = {
            "execute_python": "execute_python",
            "execute_js":     "execute_js",
            "reflect":        "reflect",
        }
        fixed_count = 0
        for res in fix_results:
            print(f"\n  🔧 Fixing: {res['bug_title']}  [{res['filename']}]")
            print(f"     Mode: {_MODE_LABEL.get(res['mode'], res['mode'])}")
            if res["status"] == "fixed":
                fixed_count += 1
                verification = res["verification"]
                print(f"     ✅ Fixed in {res['attempts']} attempt(s) — {verification}")
            else:
                print(f"     ❌ Could not fix automatically after {res['attempts']} attempt(s)")

        print(f"\n  Fixed {fixed_count}/{len(fix_results)} bugs automatically")

    # ── Security Auditor ───────────────────────────────────────────────────────
    vulns: list[dict] = []
    if "security_auditor" in plan_result["activated_agents"]:
        print("\n" + "─" * 60)
        print("🔒 Security Auditor running...")
        focus = plan_result["focus_areas"].get("security_auditor", "general security audit")

        vulns = audit_security(focus)

        _SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}
        for vuln in vulns:
            sev  = vuln["severity"].lower()
            icon = _SEVERITY_ICON.get(sev, "⚪")
            print(f"\n  {icon} [{sev.upper()}] {vuln['title']}")
            print(f"     File: {vuln['filename']} :: {vuln['function_name']}"
                  + (f" (line {vuln['line']})" if vuln["line"] else ""))
            print(f"     {vuln['description']}")
            if vuln["vulnerable_code"]:
                print(f"     Vulnerable : {vuln['vulnerable_code'][:120]}")
            if vuln["secure_fix"]:
                print(f"     Fix        : {vuln['secure_fix'][:120]}")

        print(f"\n  Found {len(vulns)} vulnerability/vulnerabilities")

    # ── Doc Checker ────────────────────────────────────────────────────────────
    doc_result: dict = {}
    if "doc_checker" in plan_result["activated_agents"]:
        print("\n" + "─" * 60)
        print("📝 Doc Checker running...")
        doc_result = check_docs(
            parsed=parsed,
            files=files,
            py_missing_doc=py_missing,
            py_total_funcs=len(py_funcs),
            js_missing_doc=js_missing,
            js_total_funcs=len(js_funcs),
        )

        # Documentation score bar
        score     = doc_result.get("documentation_score", 0)
        filled    = round(score / 10)
        bar       = "█" * filled + "░" * (10 - filled)
        print(f"\n  Documentation score: {score}/100  {bar}")

        # README assessment
        readme  = doc_result.get("readme_assessment", {})
        quality = readme.get("quality", "unknown")
        words   = readme.get("word_count", 0)
        print(f"\n  README quality: {quality}  ({words} words)")
        checklist = [
            ("has_description",  "Project description"),
            ("has_setup",        "Setup instructions"),
            ("has_usage",        "Usage examples"),
            ("has_api_docs",     "API documentation"),
            ("has_env_vars",     "Environment variables"),
            ("has_contributing", "Contributing guidelines"),
        ]
        for key, label in checklist:
            icon = "✅" if readme.get(key) else "❌"
            print(f"    {icon} {label}")

        # Top 5 most critical findings
        findings = doc_result.get("findings", [])
        _SEV_ORDER = {"critical": 0, "warning": 1, "suggestion": 2}
        top5 = sorted(findings, key=lambda f: _SEV_ORDER.get(f.get("severity", "suggestion"), 2))[:5]

        _SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}
        if top5:
            print("\n  Top findings:")
        for finding in top5:
            sev  = finding.get("severity", "suggestion").lower()
            icon = _SEVERITY_ICON.get(sev, "⚪")
            print(f"\n    {icon} [{sev.upper()}] {finding.get('title', '')}")
            print(f"       {finding.get('filename', '')} :: {finding.get('function_name', '')} (line {finding.get('line', '?')})")
            print(f"       {finding.get('description', '')}")

        summary = doc_result.get("summary", "")
        if summary:
            print(f"\n  Summary: {summary}")

    # ── Code Quality ───────────────────────────────────────────────────────────
    quality_result: dict = {}
    if "code_quality" in plan_result["activated_agents"]:
        print("\n" + "─" * 60)
        print("⚙️  Code Quality Agent running...")
        focus = plan_result["focus_areas"].get("code_quality", "general code quality review")

        quality_result = analyze_quality(focus, parsed, files)

        # Quality score bar
        qscore  = quality_result.get("overall_quality_score", 0)
        qfilled = round(qscore / 10)
        qbar    = "█" * qfilled + "░" * (10 - qfilled)
        print(f"\n  Overall quality score: {qscore}/100  {qbar}")

        # Top 3 longest functions
        longest = quality_result.get("longest_functions", [])[:3]
        if longest:
            print("\n  Longest functions:")
            for fn in longest:
                print(f"    {fn['approx_lines']:>4} lines  {fn['filename']} :: {fn['function_name']} (line {fn['line']})")

        # Deduplicate combined issues by (filename, function_name, issue_type)
        # then take top 5 sorted by severity
        all_issues = quality_result.get("issues", [])
        _seen_issue_keys: set[tuple] = set()
        _deduped_issues: list[dict] = []
        for _iss in all_issues:
            _k = (_iss.get("filename"), _iss.get("function_name"), _iss.get("issue_type"))
            if _k not in _seen_issue_keys:
                _seen_issue_keys.add(_k)
                _deduped_issues.append(_iss)

        _SEV_ORDER = {"critical": 0, "warning": 1, "suggestion": 2}
        top5 = sorted(
            _deduped_issues,
            key=lambda x: _SEV_ORDER.get(x.get("severity", "suggestion"), 2),
        )[:5]

        _SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}
        if top5:
            print("\n  Top issues:")
        for issue in top5:
            sev  = issue.get("severity", "warning").lower()
            icon = _SEVERITY_ICON.get(sev, "⚪")
            itype = issue.get("issue_type", "")
            print(f"\n    {icon} [{sev.upper()}] [{itype}] {issue.get('title', '')}")
            print(f"       {issue.get('filename', '')} :: {issue.get('function_name', '')}"
                  + (f" (line {issue['line']})" if issue.get("line") else ""))
            print(f"       {issue.get('description', '')}")

        qsummary = quality_result.get("summary", "")
        if qsummary:
            print(f"\n  Summary: {qsummary}")

    # ── Synthesizer ────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("📊 Synthesizer generating final report...")

    report = synthesize(
        repo_url           = GITHUB_REPO_URL,
        files              = files,
        language_breakdown = language_breakdown,
        total_functions    = total_funcs,
        orchestrator       = summary,
        planner            = plan_result,
        bugs               = bugs,
        vulnerabilities    = vulns,
        doc_findings       = doc_result,
        quality_issues     = quality_result,
        fixes              = fix_results,
    )

    # ── Save JSON report ───────────────────────────────────────────────────────
    os.makedirs("review_output", exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join("review_output", f"report_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved → {out_path}")

    # ── Pretty box summary ─────────────────────────────────────────────────────
    _W   = 56          # interior width
    _TOP = "╔" + "═" * _W + "╗"
    _MID = "╠" + "═" * _W + "╣"
    _BOT = "╚" + "═" * _W + "╝"

    def _row(text: str = "") -> str:
        return "║  " + text.ljust(_W - 2) + "║"

    repo_name  = GITHUB_REPO_URL.rstrip("/").split("/")[-1]
    s          = report["summary"]
    health     = s.get("overall_health", "unknown").upper()
    hscore     = s.get("health_score", 0)
    meta       = report["metadata"]

    bug_counts  = {"critical": 0, "warning": 0, "suggestion": 0}
    for b in bugs:
        sev = b.get("severity", "warning").lower()
        if sev in bug_counts:
            bug_counts[sev] += 1

    vuln_counts = {"critical": 0, "warning": 0}
    for v in vulns:
        sev = v.get("severity", "warning").lower()
        if sev in vuln_counts:
            vuln_counts[sev] += 1

    doc_score     = doc_result.get("documentation_score", 0)
    quality_score = quality_result.get("overall_quality_score", 0)
    fixed_count   = sum(1 for fx in fix_results if fx.get("status") == "fixed")

    priorities = s.get("top_priorities", [])
    verdict    = s.get("verdict", "")

    # Word-wrap verdict at 52 chars
    _VW = _W - 4
    verdict_lines: list[str] = []
    words = verdict.split()
    line  = ""
    for word in words:
        if len(line) + len(word) + (1 if line else 0) <= _VW:
            line = (line + " " + word).lstrip()
        else:
            if line:
                verdict_lines.append(line)
            line = word
    if line:
        verdict_lines.append(line)

    print()
    print(_TOP)
    print(_row(f"CODE REVIEW COMPLETE — {repo_name}"))
    print(_MID)
    print(_row(f"Overall Health:  {health}  ({hscore}/100)"))
    print(_row(f"Files Analyzed:  {meta['total_files']}"))
    print(_row(f"Functions Found: {meta['total_functions']}"))
    print(_MID)
    print(_row("FINDINGS"))
    print(_row(
        f"🔴 Bugs:            {len(bugs)}"
        + (f"  ({bug_counts['critical']} critical, {bug_counts['warning']} warning)" if bugs else "")
    ))
    print(_row(
        f"🔒 Vulnerabilities: {len(vulns)}"
        + (f"  ({vuln_counts['critical']} critical)" if vulns else "")
    ))
    print(_row(f"📝 Doc Score:       {doc_score}/100"))
    print(_row(f"⚙️  Quality Score:   {quality_score}/100"))
    print(_row(f"🔧 Auto-fixed:      {fixed_count}/{len(fix_results)} bugs"))
    print(_MID)
    print(_row("TOP PRIORITIES"))
    for i, priority in enumerate(priorities[:3], start=1):
        # Truncate priority text to fit
        text = f"{i}. {priority}"
        if len(text) > _W - 2:
            text = text[: _W - 5] + "..."
        print(_row(text))
    print(_MID)
    print(_row("VERDICT"))
    for vline in verdict_lines:
        print(_row(vline))
    print(_BOT)
    print()


if __name__ == "__main__":
    main()
