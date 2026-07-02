"""Check the human-facing Progress dashboard for log-like bloat."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, read_text


PROGRESS_RELATIVE = "Harness/Progress.md"
DATE_PATTERN = re.compile(r"20\d\d[-./]\d\d[-./]\d\d")
DATE_LOG_LINE_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?(?:#+\s*)?20\d\d[-./]\d\d[-./]\d\d", re.MULTILINE)
# A single `Last updated:` header (seconds precision) makes worktree merge
# conflicts on this replace-in-place dashboard trivial to resolve: keep the
# block with the newest timestamp. It is a header, not a date-log entry.
LAST_UPDATED_LINE_PATTERN = re.compile(r"(?im)^\s*\**\s*Last updated:\**\s*(.*?)\s*$")
LAST_UPDATED_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")
HARD_LINE_LIMIT = 40
MAX_SECTION_BULLETS = 3
ALLOWED_SECTIONS = ["현재 상태", "최근 완료", "확인 필요", "다음 작업"]


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


def _level_two_sections(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def build_report(root: Path) -> dict:
    path = root / PROGRESS_RELATIVE
    text = read_text(path)
    lines = text.splitlines()
    date_count = len(DATE_PATTERN.findall(text))
    date_log_line_count = len(DATE_LOG_LINE_PATTERN.findall(text))
    sections = _level_two_sections(text)
    section_bullets = {section: _bullet_count(_section_lines(text, f"## {section}")) for section in sections}
    warnings: list[str] = []
    errors: list[str] = []

    last_updated_match = LAST_UPDATED_LINE_PATTERN.search(text)
    last_updated_value = last_updated_match.group(1).strip() if last_updated_match else ""
    timestamp_match = LAST_UPDATED_TIMESTAMP_PATTERN.search(last_updated_value) if last_updated_value else None
    last_updated = timestamp_match.group(0) if timestamp_match else None
    if path.exists() and last_updated_match is None:
        warnings.append("missing_last_updated_header")

    if not path.exists():
        errors.append("missing")
    if len(lines) > HARD_LINE_LIMIT:
        errors.append(f"longer_than_hard_limit:{HARD_LINE_LIMIT}")
    missing_sections = [section for section in ALLOWED_SECTIONS if section not in sections]
    extra_sections = [section for section in sections if section not in ALLOWED_SECTIONS]
    if missing_sections:
        errors.append("missing_sections:" + ",".join(missing_sections))
    if extra_sections:
        errors.append("unexpected_sections:" + ",".join(extra_sections))
    if len(sections) != len(set(sections)):
        errors.append("duplicate_sections")
    for section, count in section_bullets.items():
        if count > MAX_SECTION_BULLETS:
            errors.append(f"section_bullets_exceed_limit:{section}:{count}>{MAX_SECTION_BULLETS}")
    if date_log_line_count > MAX_SECTION_BULLETS:
        errors.append(f"appears_to_be_date_log:{date_log_line_count}")

    return {
        "root": str(root),
        "path": PROGRESS_RELATIVE,
        "exists": path.exists(),
        "ok": not errors,
        "lines": len(lines),
        "last_updated": last_updated,
        "date_count": date_count,
        "date_log_line_count": date_log_line_count,
        "recent_completed_count": section_bullets.get("최근 완료", 0),
        "sections": sections,
        "section_bullets": section_bullets,
        "warnings": warnings,
        "errors": errors,
        "guidance": [
            "Keep Progress.md as a current dashboard, not an append-only work log.",
            "Use only 현재 상태, 최근 완료, 확인 필요, and 다음 작업, with at most three bullets each.",
            "Refresh existing bullets in place and move detailed history to Harness/work/tasks/, Harness/work/cycles/, or an archive.",
            "Stamp `**Last updated:** YYYY-MM-DD HH:MM:SS +09:00` so a worktree merge conflict is resolved by keeping the newest block.",
        ],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Progress Check",
        f"- Root: {report['root']}",
        f"- Path: {report['path']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Lines: {report['lines']}",
        f"- Last updated: {report.get('last_updated') or 'unset'}",
        f"- Dates: {report['date_count']}",
        f"- Sections: {', '.join(report['sections']) or 'none'}",
    ]
    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report["errors"]:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness/Progress.md for dashboard bloat.")
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
