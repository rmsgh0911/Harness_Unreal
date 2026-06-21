"""Prepare or append short Harness cycle log entries."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, dump_json, find_project_root, parse_date_text, read_text, rel, today_cycle_path, validate_task_id, write_text
from harness_cycle_summary import parse_cycle_file


def normalize_items(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned or [fallback]


def format_item_lines(label: str, items: list[str]) -> list[str]:
    first, *rest = items
    return [f"- {label}: {first}", *(f"  - {item}" for item in rest)]


def build_entry(
    title: str,
    changed: list[str],
    verified: list[str],
    remaining: list[str],
    worker: str = "",
    cycle_number: int | None = None,
    max_cycles: int | None = None,
    decision: str = "",
    success_criteria: list[str] | None = None,
) -> str:
    now = datetime.now().astimezone()
    lines = [f"## {now.strftime('%H:%M')} {title}", "", f"- Recorded: {now.isoformat(timespec='minutes')}"]
    if worker:
        lines.append(f"- Worker: {worker}")
    if cycle_number is not None:
        lines.append(f"- Cycle: {cycle_number}" + (f"/{max_cycles}" if max_cycles is not None else ""))
    if decision:
        lines.append(f"- Decision: {decision}")
    if success_criteria:
        lines.extend(format_item_lines("Success Criteria", normalize_items(success_criteria, "not recorded")))
    lines.extend(format_item_lines("Changed", normalize_items(changed, "record needed")))
    lines.extend(format_item_lines("Verified", normalize_items(verified, "record needed")))
    lines.extend(format_item_lines("Remaining", normalize_items(remaining, "none")))
    return "\n".join(lines) + "\n"


def append_entry(path: Path, entry: str) -> None:
    existing = read_text(path)
    separator = "\n\n" if existing else ""
    write_text(path, existing.rstrip() + separator + entry)


def entry_count(path: Path) -> int:
    return sum(1 for line in read_text(path).splitlines() if line.startswith("## "))


def validate_iteration_entry(path: Path, cycle_number: int | None, max_cycles: int | None, decision: str) -> list[str]:
    if cycle_number is None:
        return []
    parsed = parse_cycle_file(path) if path.exists() else {"sections": [], "iteration": {"warnings": []}}
    sections = parsed["sections"]
    numbered = [section for section in sections if section.get("cycle_number") is not None]
    errors = [f"existing cycle log is invalid: {warning}" for warning in parsed["iteration"]["warnings"]]
    expected = len(sections) + 1
    if cycle_number != expected:
        errors.append(f"cycle number must be the next contiguous value: {expected}")
    recorded_budgets = {section["max_cycles"] for section in numbered if section.get("max_cycles") is not None}
    if max_cycles is not None and recorded_budgets and recorded_budgets != {max_cycles}:
        errors.append(f"cycle budget must remain {next(iter(recorded_budgets))}")
    if numbered and numbered[-1].get("decision", "").startswith("stop_"):
        errors.append("cannot append after a stop decision")
    if max_cycles is not None and not decision:
        errors.append("--decision is required when --max-cycles is used")
    if max_cycles is not None and cycle_number == max_cycles and decision == "continue":
        errors.append("the final budgeted cycle must use stop_success or stop_blocked")
    return errors


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
    parser.add_argument("--cycle-number", type=int, default=None, help="Cycle number. Defaults to the next entry number for the selected file.")
    parser.add_argument("--max-cycles", type=int, default=None, help="Optional cycle budget recorded as N/max.")
    parser.add_argument("--decision", choices=["continue", "stop_success", "stop_blocked"], default="", help="Decision at the end of this cycle.")
    parser.add_argument("--success-criterion", action="append", default=[], help="Success criterion this cycle is working toward. Can be repeated.")
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

    cycle_number = args.cycle_number
    if cycle_number is None and (args.task or args.max_cycles is not None or args.decision):
        cycle_number = entry_count(path) + 1
    if args.max_cycles is not None and args.max_cycles < 1:
        parser.error("--max-cycles must be at least 1")
    if cycle_number is not None and cycle_number < 1:
        parser.error("--cycle-number must be at least 1")
    if cycle_number is not None and args.max_cycles is not None and cycle_number > args.max_cycles:
        parser.error("--cycle-number cannot exceed --max-cycles")
    iteration_errors = validate_iteration_entry(path, cycle_number, args.max_cycles, args.decision)
    if iteration_errors:
        parser.error("; ".join(iteration_errors))
    entry = build_entry(
        args.title,
        args.changed,
        args.verified,
        args.remaining,
        args.worker,
        cycle_number=cycle_number,
        max_cycles=args.max_cycles,
        decision=args.decision,
        success_criteria=args.success_criterion,
    )
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
