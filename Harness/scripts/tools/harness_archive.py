"""Preview or archive completed task records and old date-based cycle records."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, dump_json, find_project_root, read_text, rel, task_cycle_path, task_path, validate_task_id


COMPLETED_STATUS_PATTERN = re.compile(r"^\s*-\s*Status:\s*(completed|complete|done|closed)\s*$", re.IGNORECASE | re.MULTILINE)
ARCHIVE_MONTH_PATTERN = re.compile(r"20\d\d-(0[1-9]|1[0-2])")
DATE_CYCLE_PATTERN = re.compile(r"(20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))")


def validate_archive_month(month: str) -> str:
    if month and not ARCHIVE_MONTH_PATTERN.fullmatch(month):
        raise ValueError("archive month must use YYYY-MM")
    return month


def build_plan(root: Path, task: str, month: str = "") -> dict:
    validate_task_id(task)
    validate_archive_month(month)
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
        "mode": "task",
        "root": str(root),
        "task": task,
        "archive_month": archive_month,
        "destination": rel(destination, root),
        "sources": [
            {
                "path": rel(path, root),
                "kind": "tasks" if path == task_file else "cycles",
                "month": archive_month,
            }
            for path in sources
        ],
        "errors": errors,
        "ready": not errors,
    }


def build_before_plan(root: Path, before: str) -> dict:
    """Plan archiving of date-named cycle files older than the given month.

    Date-based cycle files such as `2026-06-17.md` or `claude-2026-05-08.md`
    have no task record, so task-based archiving can never move them. Each
    file is archived into the monthly folder matching its own date.
    """
    errors: list[str] = []
    try:
        validate_archive_month(before)
        if not before:
            raise ValueError("archive month must use YYYY-MM")
    except ValueError as exc:
        errors.append(str(exc))
        before = ""
    cycles = cycles_dir(root)
    sources: list[dict] = []
    if before:
        for path in sorted(cycles.glob("*.md")) if cycles.exists() else []:
            match = DATE_CYCLE_PATTERN.search(path.stem)
            if not match:
                continue
            month = match.group(1)[:7]
            if month < before:
                sources.append({"path": rel(path, root), "kind": "cycles", "month": month})
        if not sources:
            errors.append(f"no date-based cycle records older than {before}")
    return {
        "mode": "before",
        "root": str(root),
        "before": before,
        "destination": rel(root / "Harness" / "work" / "archive", root),
        "sources": sources,
        "errors": errors,
        "ready": not errors,
    }


def rebuild_plan(root: Path, plan: dict) -> dict:
    if plan.get("mode") == "before":
        return build_before_plan(root, str(plan.get("before", "")))
    return build_plan(root, str(plan.get("task", "")), str(plan.get("archive_month", "")))


def index_entries(plan: dict) -> list[str]:
    archive_root = "Harness/work/archive"
    if plan.get("mode") == "before":
        months = sorted({source["month"] for source in plan["sources"]})
        return [f"- cycles {month}: `{archive_root}/{month}/cycles/`" for month in months]
    return [f"- `{plan['task']}`: `{archive_root}/{plan['archive_month']}/`"]


def apply_archive(root: Path, plan: dict) -> list[str]:
    current = rebuild_plan(root, plan)
    if not current["ready"]:
        raise ValueError("archive plan is no longer ready: " + "; ".join(current["errors"]))
    archive_root = root / "Harness" / "work" / "archive"
    moves: list[tuple[Path, Path]] = []
    for source_item in current["sources"]:
        source = root / source_item["path"]
        target = archive_root / source_item["month"] / source_item["kind"] / source.name
        if not source.is_file():
            raise FileNotFoundError(f"archive source is missing: {rel(source, root)}")
        if target.exists():
            raise FileExistsError(f"archive target already exists: {rel(target, root)}")
        moves.append((source, target))
    index = archive_root / "index.md"
    existing = read_text(index, "# Work Archive\n\nCompleted task and cycle records remain searchable by task ID.\n")
    updated_index = existing
    for entry in index_entries(current):
        if entry.strip() not in updated_index:
            updated_index = updated_index.rstrip() + "\n\n" + entry + "\n"

    created_dirs: set[Path] = set()
    if not index.parent.exists():
        created_dirs.add(index.parent)
    index.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(prefix=".archive-index-", suffix=".tmp", dir=index.parent)
    os.close(temporary_fd)
    temporary_index = Path(temporary_name)
    temporary_index.write_text(updated_index, encoding="utf-8", newline="\n")
    moved: list[tuple[Path, Path]] = []
    completed = False
    try:
        for source, target in moves:
            cursor = target.parent
            while not cursor.exists() and cursor != index.parent.parent:
                created_dirs.add(cursor)
                cursor = cursor.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, target)
            moved.append((source, target))
        os.replace(temporary_index, index)
        completed = True
    except Exception:
        for source, target in reversed(moved):
            if target.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(target, source)
        raise
    finally:
        if temporary_index.exists():
            temporary_index.unlink()
        if not completed:
            for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
                if directory.exists():
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
    return [rel(target, root) for _, target in moved]


def format_text(report: dict) -> str:
    lines = [
        "Harness Archive",
        f"- Root: {report['root']}",
    ]
    if report.get("mode") == "before":
        lines.append(f"- Cycles before: {report.get('before') or 'invalid'}")
    else:
        lines.append(f"- Task: {report['task']}")
    lines.extend(
        [
            f"- Destination: {report['destination']}",
            f"- Mode: {'archived' if report.get('archived') else 'preview'}",
        ]
    )
    lines.extend(f"- Source: {source['path']} -> {source['month']}" for source in report["sources"])
    if report["errors"]:
        lines.extend(["", "Errors:", *(f"- {error}" for error in report["errors"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or archive completed task records and old date-based cycle records.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--task", type=validate_task_id, default="", help="Completed task ID to archive with its task-scoped cycle file.")
    parser.add_argument("--before", default="", help="Archive date-named cycle files older than this YYYY-MM month into monthly folders.")
    parser.add_argument("--month", default="", help="Archive month in YYYY-MM form for --task mode. Defaults to the current month.")
    parser.add_argument("--archive", action="store_true", help="Move records and update the archive index. Without this flag, only preview.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if bool(args.task) == bool(args.before):
        parser.error("use exactly one of --task or --before")
    if args.before and args.month:
        parser.error("--month applies only to --task mode")
    try:
        validate_archive_month(args.month)
        if args.before:
            validate_archive_month(args.before)
    except ValueError as exc:
        parser.error(str(exc))
    root = find_project_root(args.root)
    report = build_before_plan(root, args.before) if args.before else build_plan(root, args.task, args.month)
    report["archived"] = False
    report["moved"] = []
    if args.archive and report["ready"]:
        report["moved"] = apply_archive(root, report)
        report["archived"] = True
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
