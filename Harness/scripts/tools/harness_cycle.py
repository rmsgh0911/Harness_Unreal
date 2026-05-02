"""Prepare or append short Harness cycle log entries."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, parse_date_text, read_text, rel, today_cycle_path, write_text


def build_entry(title: str, changed: str, verified: str, remaining: str, now: datetime | None = None) -> str:
    time_text = (now or datetime.now()).strftime("%H:%M")
    return (
        f"## {time_text} {title}\n\n"
        f"- 변경: {changed or '작성 필요'}\n"
        f"- 검증: {verified or '작성 필요'}\n"
        f"- 남은 것: {remaining or '없음'}\n"
    )


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
    parser.add_argument("--changed", default="", help="What changed.")
    parser.add_argument("--verified", default="", help="What was verified.")
    parser.add_argument("--remaining", default="", help="Remaining work or risk.")
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
