"""Prepare or append short Harness cycle log entries."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, dump_json, find_project_root, parse_date_text, read_text, rel, today_cycle_path, validate_task_id, write_text


def normalize_items(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned or [fallback]


def format_item_lines(label: str, items: list[str]) -> list[str]:
    first, *rest = items
    return [f"- {label}: {first}", *(f"  - {item}" for item in rest)]


def build_entry(title: str, changed: list[str], verified: list[str], remaining: list[str], worker: str = "") -> str:
    now = datetime.now().astimezone()
    lines = [f"## {now.strftime('%H:%M')} {title}", "", f"- Recorded: {now.isoformat(timespec='minutes')}"]
    if worker:
        lines.append(f"- Worker: {worker}")
    lines.extend(format_item_lines("Changed", normalize_items(changed, "record needed")))
    lines.extend(format_item_lines("Verified", normalize_items(verified, "record needed")))
    lines.extend(format_item_lines("Remaining", normalize_items(remaining, "none")))
    return "\n".join(lines) + "\n"


def append_entry(path: Path, entry: str) -> None:
    existing = read_text(path)
    separator = "\n\n" if existing else ""
    write_text(path, existing.rstrip() + separator + entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a short Harness cycle log entry.")
    parser.add_argument("title", help="Cycle title.")
    parser.add_argument("--changed", action="append", default=[], help="What changed. Can be repeated.")
    parser.add_argument("--verified", action="append", default=[], help="What was verified. Can be repeated.")
    parser.add_argument("--remaining", action="append", default=[], help="Remaining work or risk. Can be repeated.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--date", default="", help="Cycle date as YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Task ID. Writes to cycles/<task-id>.md and is recommended for parallel work.")
    parser.add_argument("--worker", default="", help="Agent or worker name recorded in the entry.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--write", action="store_true", help="Append to the selected Harness/work/cycles file.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    path = today_cycle_path(root)
    if args.task:
        path = cycles_dir(root) / f"{args.task}.md"
    if args.date:
        if args.task:
            parser.error("--date and --task cannot be used together")
        try:
            path = cycles_dir(root) / f"{parse_date_text(args.date)}.md"
        except ValueError:
            parser.error("--date must be in YYYY-MM-DD format")

    entry = build_entry(args.title, args.changed, args.verified, args.remaining, args.worker)
    result = {"root": str(root), "path": rel(path, root), "write": args.write, "entry": entry}
    if args.write:
        append_entry(path, entry)
        result["status"] = "written"
    else:
        result["status"] = "dry_run"

    if args.json:
        print(dump_json(result))
    elif args.write:
        print(f"Appended cycle entry: {path}")
    else:
        print(entry.rstrip())
        print(f"\nDry run only. Add --write to append to {path}")


if __name__ == "__main__":
    main()
