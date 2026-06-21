"""Preview or archive a completed task and its cycle record."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, read_text, rel, task_cycle_path, task_path, validate_task_id, write_text


COMPLETED_STATUS_PATTERN = re.compile(r"^\s*-\s*Status:\s*(completed|complete|done|closed)\s*$", re.IGNORECASE | re.MULTILINE)


def build_plan(root: Path, task: str, month: str = "") -> dict:
    task_file = task_path(root, task)
    cycle_file = task_cycle_path(root, task)
    archive_month = month or datetime.now().strftime("%Y-%m")
    destination = root / "Harness" / "work" / "archive" / archive_month
    sources = [path for path in [task_file, cycle_file] if path.exists()]
    errors: list[str] = []
    if not task_file.exists():
        errors.append(f"task record is missing: {rel(task_file, root)}")
    elif not COMPLETED_STATUS_PATTERN.search(read_text(task_file)):
        errors.append("task Status must be completed, complete, done, or closed before archiving")
    if not sources:
        errors.append("no task or cycle records found")
    return {
        "root": str(root),
        "task": task,
        "archive_month": archive_month,
        "destination": rel(destination, root),
        "sources": [
            {"path": rel(path, root), "kind": "tasks" if path == task_file else "cycles"}
            for path in sources
        ],
        "errors": errors,
        "ready": not errors,
    }


def apply_archive(root: Path, plan: dict) -> list[str]:
    destination = root / plan["destination"]
    moves: list[tuple[Path, Path]] = []
    for source_item in plan["sources"]:
        source = root / source_item["path"]
        target = destination / source_item["kind"] / source.name
        if target.exists():
            raise FileExistsError(f"archive target already exists: {rel(target, root)}")
        moves.append((source, target))
    moved: list[str] = []
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        moved.append(rel(target, root))
    index = root / "Harness" / "work" / "archive" / "index.md"
    existing = read_text(index, "# Work Archive\n\nCompleted task and cycle records remain searchable by task ID.\n")
    entry = f"\n- `{plan['task']}`: `{plan['destination']}/`\n"
    if entry.strip() not in existing:
        write_text(index, existing.rstrip() + "\n" + entry)
    return moved


def format_text(report: dict) -> str:
    lines = [
        "Harness Archive",
        f"- Root: {report['root']}",
        f"- Task: {report['task']}",
        f"- Destination: {report['destination']}",
        f"- Mode: {'archived' if report.get('archived') else 'preview'}",
    ]
    lines.extend(f"- Source: {source['path']}" for source in report["sources"])
    if report["errors"]:
        lines.extend(["", "Errors:", *(f"- {error}" for error in report["errors"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or archive completed task/cycle records by task ID.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--task", required=True, type=validate_task_id, help="Completed task ID to archive.")
    parser.add_argument("--month", default="", help="Archive month in YYYY-MM form. Defaults to the current month.")
    parser.add_argument("--archive", action="store_true", help="Move records and update the archive index. Without this flag, only preview.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if args.month and not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", args.month):
        parser.error("--month must use YYYY-MM")
    root = find_project_root(args.root)
    report = build_plan(root, args.task, args.month)
    report["archived"] = False
    report["moved"] = []
    if args.archive and report["ready"]:
        report["moved"] = apply_archive(root, report)
        report["archived"] = True
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
