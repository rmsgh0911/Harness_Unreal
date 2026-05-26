"""Check the human-facing Progress dashboard for log-like bloat."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, read_text


PROGRESS_RELATIVE = "Harness/docs/Progress.md"
DATE_PATTERN = re.compile(r"20\d\d[-./]\d\d[-./]\d\d")
SOFT_LINE_LIMIT = 80
HARD_LINE_LIMIT = 140
SOFT_DATE_LIMIT = 6
SOFT_RECENT_COMPLETED_LIMIT = 8


def _section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## "):
            capture = line.strip() == heading
            continue
        if capture:
            collected.append(line)
    return collected


def _bullet_count(lines: list[str]) -> int:
    return sum(1 for line in lines if line.strip().startswith("- "))


def build_report(root: Path) -> dict:
    path = harness_dir(root) / "docs" / "Progress.md"
    text = read_text(path)
    lines = text.splitlines()
    date_count = len(DATE_PATTERN.findall(text))
    recent_completed = _bullet_count(_section_lines(text, "## 최근 완료"))
    warnings: list[str] = []
    errors: list[str] = []

    if not path.exists():
        errors.append("missing")
    if len(lines) > SOFT_LINE_LIMIT:
        warnings.append(f"longer_than_soft_limit:{SOFT_LINE_LIMIT}")
    if len(lines) > HARD_LINE_LIMIT:
        errors.append(f"longer_than_hard_limit:{HARD_LINE_LIMIT}")
    if date_count > SOFT_DATE_LIMIT:
        warnings.append(f"many_dates:{date_count}")
    if recent_completed > SOFT_RECENT_COMPLETED_LIMIT:
        warnings.append(f"recent_completed_too_long:{recent_completed}")

    return {
        "root": str(root),
        "path": PROGRESS_RELATIVE,
        "exists": path.exists(),
        "ok": not errors,
        "lines": len(lines),
        "date_count": date_count,
        "recent_completed_count": recent_completed,
        "warnings": warnings,
        "errors": errors,
        "guidance": [
            "Keep Progress.md as a current dashboard, not an append-only work log.",
            "Refresh existing bullets in place and move detailed history to Harness/work/cycles/.",
        ],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Progress Check",
        f"- Root: {report['root']}",
        f"- Path: {report['path']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Lines: {report['lines']}",
        f"- Dates: {report['date_count']}",
        f"- Recent completed bullets: {report['recent_completed_count']}",
    ]
    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report["errors"]:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness/docs/Progress.md for dashboard bloat.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
