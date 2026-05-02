"""Check Harness state/next/cycle documents for bloat and stale structure."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel


HISTORY_HINTS = [
    "On 20",
    "migrated",
    "migration",
    "이식",
    "제거",
    "추가했다",
    "변경:",
    "검증:",
    "남은 것:",
]
_DATE_PATTERN = re.compile(r"20\d\d-\d\d-\d\d")
UNRESOLVED_HINTS = ["작성 필요", "TODO", "TBD"]
OLD_PATH_HINTS = [
    "Harness/scripts/verify_project.py",
    "Harness/scripts/create_level.py",
    "Harness/scripts/build_verify.ps1",
    "Harness/scripts/build_verify.cmd",
]


def line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def count_hits(text: str, hints: list[str]) -> int:
    return sum(text.count(hint) for hint in hints)


def is_template_unconfigured(root: Path) -> bool:
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    project_configured = bool(project.get("project_name") and project.get("uproject_file")) if isinstance(project, dict) else False
    return not project_configured and not list(root.glob("*.uproject"))


def check_file(root: Path, relative: str, soft_limit: int, hard_limit: int, allow_placeholders: bool = False) -> dict:
    path = root / relative
    text = read_text(path)
    lines = line_count(text)
    warnings: list[str] = []
    errors: list[str] = []
    if not path.exists():
        warnings.append("missing")
    if lines > soft_limit:
        warnings.append(f"longer_than_soft_limit:{soft_limit}")
    if lines > hard_limit:
        errors.append(f"longer_than_hard_limit:{hard_limit}")
    unresolved = count_hits(text, UNRESOLVED_HINTS)
    old_paths = count_hits(text, OLD_PATH_HINTS)
    if unresolved and not allow_placeholders:
        warnings.append(f"unresolved_placeholders:{unresolved}")
    if old_paths:
        warnings.append(f"old_script_paths:{old_paths}")
    return {
        "path": relative,
        "exists": path.exists(),
        "lines": lines,
        "chars": len(text),
        "warnings": warnings,
        "errors": errors,
    }


def state_specific(root: Path) -> dict:
    relative = "Harness/state.md"
    text = read_text(root / relative)
    history_hits = count_hits(text, HISTORY_HINTS) + len(_DATE_PATTERN.findall(text))
    return {
        "path": relative,
        "history_hint_count": history_hits,
        "looks_like_work_log": history_hits >= 8,
    }


def cycle_summary(root: Path) -> dict:
    cycles = harness_dir(root) / "cycles"
    files = sorted(path for path in cycles.glob("*.md") if path.name != ".gitkeep") if cycles.exists() else []
    large_files: list[dict] = []
    total_lines = 0
    for path in files:
        text = read_text(path)
        lines = line_count(text)
        total_lines += lines
        if lines > 250:
            large_files.append({"path": rel(path, root), "lines": lines})
    return {
        "file_count": len(files),
        "total_lines": total_lines,
        "large_files": large_files,
    }


def build_report(root: Path) -> dict:
    template_unconfigured = is_template_unconfigured(root)
    docs = [
        check_file(root, "Harness/state.md", soft_limit=140, hard_limit=220, allow_placeholders=template_unconfigured),
        check_file(root, "Harness/next.md", soft_limit=100, hard_limit=160, allow_placeholders=template_unconfigured),
        check_file(root, "Harness/README.md", soft_limit=160, hard_limit=260),
    ]
    state = state_specific(root)
    cycles = cycle_summary(root)
    findings: list[dict] = []
    for doc in docs:
        for error in doc["errors"]:
            findings.append({"level": "error", "path": doc["path"], "message": error})
        for warning in doc["warnings"]:
            findings.append({"level": "warning", "path": doc["path"], "message": warning})
    if state["looks_like_work_log"]:
        findings.append({"level": "warning", "path": state["path"], "message": "state.md appears to contain work-log or migration history"})
    if cycles["large_files"]:
        findings.append({"level": "info", "path": "Harness/cycles/", "message": f"large cycle files: {len(cycles['large_files'])}"})
    return {
        "root": str(root),
        "ok": not any(item["level"] == "error" for item in findings),
        "template_unconfigured": template_unconfigured,
        "docs": docs,
        "state": state,
        "cycles": cycles,
        "findings": findings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness State Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Cycle files: {report['cycles']['file_count']}",
        f"- Cycle total lines: {report['cycles']['total_lines']}",
    ]
    lines.append("")
    lines.append("Docs:")
    for doc in report["docs"]:
        warn = ", ".join(doc["warnings"]) if doc["warnings"] else "ok"
        lines.append(f"- {doc['path']}: {doc['lines']} lines, {warn}")
    if report["findings"]:
        lines.append("")
        lines.append("Findings:")
        lines.extend(f"- [{item['level']}] {item['path']}: {item['message']}" for item in report["findings"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness docs for bloat, stale paths, and misplaced history.")
    parser.add_argument("--target", type=Path, default=None, help="Target project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = args.target.resolve() if args.target else find_project_root()
    report = build_report(root)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
