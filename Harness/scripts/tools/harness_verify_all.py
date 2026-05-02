"""Run the standard lightweight Harness verification bundle."""

from __future__ import annotations

import argparse
import py_compile
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, rel
from harness_context import build_context
from harness_diff_guard import build_report as build_diff_report
from harness_doctor import run_doctor
from harness_state_check import build_report as build_doc_report
from harness_docs_check import build_report as build_docs_report
from harness_scan import scan


def compile_python_files(root: Path) -> dict:
    harness = harness_dir(root)
    files = [
        *sorted((harness / "scripts" / "tools").glob("*.py")),
        *sorted((harness / "scripts" / "unreal").glob("*.py")),
    ]
    failures: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="harness_pycompile_") as temp_dir:
        temp_root = Path(temp_dir)
        for path in files:
            try:
                cfile = temp_root / (rel(path, root).replace("/", "_") + ".pyc")
                py_compile.compile(str(path), cfile=str(cfile), doraise=True)
            except py_compile.PyCompileError as exc:
                failures.append({"path": rel(path, root), "error": str(exc)})
    return {
        "ok": not failures,
        "checked": [rel(path, root) for path in files],
        "failures": failures,
    }


def check_json_files(root: Path) -> dict:
    json_paths = sorted((harness_dir(root) / "config").glob("*.json"))
    json_paths.append(harness_dir(root) / "scripts" / "tools" / "tool_manifest.json")
    failures: list[dict] = []
    for path in json_paths:
        try:
            load_json(path, {})
        except Exception as exc:  # noqa: BLE001
            failures.append({"path": rel(path, root), "error": str(exc)})
    return {
        "ok": not failures,
        "checked": [rel(path, root) for path in json_paths],
        "failures": failures,
    }


def check_build_readiness(root: Path) -> dict:
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    build = project.get("build", {}) if isinstance(project, dict) else {}
    missing: list[str] = []
    for key in ["engine_root", "editor_target_name"]:
        if not build.get(key):
            missing.append(f"build.{key}")
    if not project.get("uproject_file"):
        missing.append("uproject_file")

    build_cmd = harness_dir(root) / "scripts" / "build" / "build_verify.cmd"
    return {
        "ok": not missing and build_cmd.exists(),
        "command": "Harness/scripts/build/build_verify.cmd -Mode Editor",
        "missing": missing,
        "status": "ready" if not missing and build_cmd.exists() else "skipped_or_incomplete",
    }


def build_verify_all(root: Path, include_assets: bool = False, compile_python: bool = True) -> dict:
    doctor = run_doctor(root)
    context = build_context(root)
    scan_report = scan(root, include_assets=include_assets)
    diff = build_diff_report(root)
    doc_check = build_doc_report(root)
    docs_check = build_docs_report(root)
    json_check = check_json_files(root)
    compile_check = compile_python_files(root) if compile_python else {"ok": True, "checked": [], "failures": [], "skipped": True}
    build_readiness = check_build_readiness(root)

    hard_ok = doctor["ok"] and docs_check["ok"] and json_check["ok"] and compile_check["ok"] and doc_check["ok"]
    return {
        "root": str(root),
        "ok": hard_ok,
        "summary": {
            "doctor": "ok" if doctor["ok"] else "failed",
            "doctor_warnings": doctor["summary"].get("warnings", 0),
            "json": "ok" if json_check["ok"] else "failed",
            "python_compile": "ok" if compile_check["ok"] else "failed",
            "scan": "ok",
            "diff_guard": "ok" if diff["ok"] else "needs_attention",
            "state_check": "ok" if doc_check["ok"] else "failed",
            "docs_check": "ok" if docs_check["ok"] else "failed",
            "build": build_readiness["status"],
        },
        "context_warnings": context.get("warnings", []),
        "doctor": doctor["summary"],
        "json_check": json_check,
        "python_compile": compile_check,
        "scan": {
            "uproject_count": len(scan_report["uprojects"]),
            "module_count": len(scan_report["source"]["modules"]),
            "plugin_count": len(scan_report["plugins"]["uplugin_files"]),
            "map_count": len(scan_report["content"]["map_files"]),
            "include_assets": include_assets,
        },
        "diff_guard": {
            "git_available": diff["git_available"],
            "mode": diff["mode"],
            "risk_count": diff["risk_count"],
            "change_list_reliable": diff["change_list_reliable"],
        },
        "doc_check": {
            "finding_count": len(doc_check["findings"]),
            "cycle_files": doc_check["cycles"]["file_count"],
            "cycle_total_lines": doc_check["cycles"]["total_lines"],
        },
        "docs_check": {
            "finding_count": len(docs_check["findings"]),
            "doc_roots": docs_check["summary"]["doc_roots"],
            "entry_points": docs_check["summary"]["entry_points"],
            "markdown_files": docs_check["summary"]["markdown_files"],
        },
        "build_readiness": build_readiness,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Verify All",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Doctor: {report['summary']['doctor']}",
        f"- Doctor warnings: {report['summary']['doctor_warnings']}",
        f"- JSON: {report['summary']['json']}",
        f"- Python compile: {report['summary']['python_compile']}",
        f"- Scan: {report['summary']['scan']}",
        f"- Diff guard: {report['summary']['diff_guard']} ({report['diff_guard']['mode']})",
        f"- State check (state/next/cycles 길이·포맷): {report['summary']['state_check']}",
        f"- Docs policy (문서 루트 발견·읽기정책): {report['summary']['docs_check']}",
        f"- Build: {report['summary']['build']}",
    ]
    if report["context_warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report["context_warnings"])
    if report["build_readiness"]["missing"]:
        lines.append("")
        lines.append("Build readiness missing:")
        lines.extend(f"- {item}" for item in report["build_readiness"]["missing"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run standard lightweight Harness verification checks.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--include-assets", action="store_true", help="Include Content/*.umap in scan.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip Python compile checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_verify_all(root, include_assets=args.include_assets, compile_python=not args.skip_compile)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
