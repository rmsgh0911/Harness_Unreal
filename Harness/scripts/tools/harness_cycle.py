"""Prepare or append short Harness cycle log entries."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, parse_date_text, read_text, rel, today_cycle_path, write_text


def normalize_items(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned or [fallback]


def format_item_lines(label: str, items: list[str]) -> list[str]:
    first, *rest = items
    lines = [f"- {label}: {first}"]
    lines.extend(f"  - {item}" for item in rest)
    return lines


def build_entry(
    title: str,
    changed: list[str] | None = None,
    verified: list[str] | None = None,
    remaining: list[str] | None = None,
    now: datetime | None = None,
) -> str:
    time_text = (now or datetime.now()).strftime("%H:%M")
    changed_items = normalize_items(changed or [], "작성 필요")
    verified_items = normalize_items(verified or [], "작성 필요")
    remaining_items = normalize_items(remaining or [], "없음")
    lines = [
        f"## {time_text} {title}",
        "",
        *format_item_lines("변경", changed_items),
        *format_item_lines("검증", verified_items),
        *format_item_lines("남은 것", remaining_items),
    ]
    return "\n".join(lines) + "\n"


def append_entry(path: Path, entry: str) -> None:
    existing = read_text(path)
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing:
        existing += "\n"
    write_text(path, existing + entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a short Harness cycle log entry.")
    parser.add_argument("title", help="Cycle title.")
    parser.add_argument("--changed", action="append", default=[], help="What changed. Can be repeated.")
    parser.add_argument("--verified", action="append", default=[], help="What was verified. Can be repeated.")
    parser.add_argument("--remaining", action="append", default=[], help="Remaining work or risk. Can be repeated.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--date", default="", help="Cycle date as YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--write", action="store_true", help="Append to Harness/cycles/YYYY-MM-DD.md.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    path = today_cycle_path(root)
    if args.date:
        try:
            date_text = parse_date_text(args.date)
        except ValueError:
            parser.error("--date must be in YYYY-MM-DD format")
        path = root / "Harness" / "cycles" / f"{date_text}.md"

    entry = build_entry(args.title, args.changed, args.verified, args.remaining)
    result = {
        "root": str(root),
        "path": rel(path, root),
        "write": args.write,
        "entry": entry,
    }
    if args.write:
        append_entry(path, entry)
        result["status"] = "written"
    else:
        result["status"] = "dry_run"

    if args.json:
        print(dump_json(result))
        return

    if args.write:
        print(f"Appended cycle entry: {path}")
    else:
        print(entry.rstrip())
        print("")
        print(f"Dry run only. Add --write to append to {path}")


if __name__ == "__main__":
    main()
