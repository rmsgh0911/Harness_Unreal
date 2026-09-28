"""Preview or atomically close and archive one task/cycle record pair."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_archive import apply_archive, build_plan as build_archive_plan, validate_archive_month
from harness_common import dump_json, find_project_root, read_text, rel, task_cycle_path, task_path, validate_task_id
from harness_cycle_summary import EVIDENCE_GAP_STATUSES, parse_cycle_file, unique_recorded


STATUS_PATTERN = re.compile(r"^(\s*-\s*Status:\s*).+$", re.IGNORECASE | re.MULTILINE)
UPDATED_PATTERN = re.compile(r"^(\s*-\s*Updated:\s*).+$", re.IGNORECASE | re.MULTILINE)
SUCCESS_DECISION = "stop_success"


def render_completed_task(text: str, recorded_at: datetime | None = None) -> str:
    if len(STATUS_PATTERN.findall(text)) != 1:
        raise ValueError("task record must contain exactly one Status field")
    now = recorded_at or datetime.now().astimezone()
    updated = STATUS_PATTERN.sub(r"\g<1>completed", text, count=1)
    timestamp = now.isoformat(timespec="minutes")
    if UPDATED_PATTERN.search(updated):
        updated = UPDATED_PATTERN.sub(rf"\g<1>{timestamp}", updated, count=1)
    return updated


def build_close_plan(root: Path, task: str, month: str = "") -> dict:
    validate_task_id(task)
    validate_archive_month(month)
    task_file = task_path(root, task)
    cycle_file = task_cycle_path(root, task)
    archive_month = month or datetime.now().strftime("%Y-%m")
    errors: list[str] = []
    latest: dict = {}
    if not task_file.is_file():
        errors.append(f"task record is missing: {rel(task_file, root)}")
    else:
        try:
            render_completed_task(read_text(task_file))
        except ValueError as exc:
            errors.append(str(exc))
    if not cycle_file.is_file():
        errors.append(f"cycle record is missing: {rel(cycle_file, root)}")
    else:
        parsed = parse_cycle_file(cycle_file)
        if parsed["iteration"]["warnings"]:
            errors.extend(f"cycle log is invalid: {warning}" for warning in parsed["iteration"]["warnings"])
        if parsed["sections"]:
            latest = parsed["sections"][-1]
        else:
            errors.append("cycle record has no entries")
    if latest:
        if latest.get("decision") != SUCCESS_DECISION:
            errors.append("latest cycle decision must be stop_success before closeout")
        if not unique_recorded(latest.get("verified", [])):
            errors.append("latest cycle must contain concrete verification before closeout")
        if latest.get("evidence_status") in EVIDENCE_GAP_STATUSES:
            errors.append(f"latest cycle has an unresolved evidence gap: {latest['evidence_status']}")
    destination = root / "Harness" / "work" / "archive" / archive_month
    for source, kind in ((task_file, "tasks"), (cycle_file, "cycles")):
        target = destination / kind / source.name
        if target.exists():
            errors.append(f"archive target already exists: {rel(target, root)}")
    return {
        "root": str(root),
        "task": task,
        "archive_month": archive_month,
        "task_path": rel(task_file, root),
        "cycle_path": rel(cycle_file, root),
        "latest_decision": latest.get("decision", ""),
        "evidence_status": latest.get("evidence_status", ""),
        "destination": rel(destination, root),
        "actions": ["mark task completed", "refresh task Updated field when present", "archive task and cycle transactionally"],
        "errors": errors,
        "ready": not errors,
    }


def _replace_bytes(path: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_close(root: Path, plan: dict) -> list[str]:
    current = build_close_plan(root, str(plan.get("task", "")), str(plan.get("archive_month", "")))
    if not current["ready"]:
        raise ValueError("close plan is no longer ready: " + "; ".join(current["errors"]))
    task_file = root / current["task_path"]
    original = task_file.read_bytes()
    completed = render_completed_task(original.decode("utf-8")).encode("utf-8")
    _replace_bytes(task_file, completed)
    try:
        archive_plan = build_archive_plan(root, current["task"], current["archive_month"])
        if not archive_plan["ready"]:
            raise ValueError("archive plan is not ready: " + "; ".join(archive_plan["errors"]))
        return apply_archive(root, archive_plan)
    except Exception:
        if task_file.exists():
            _replace_bytes(task_file, original)
        raise


def format_text(report: dict) -> str:
    lines = [
        "Harness Work Close",
        f"- Root: {report['root']}",
        f"- Task: {report['task']}",
        f"- Destination: {report['destination']}",
        f"- Mode: {'closed and archived' if report.get('closed') else 'preview'}",
        f"- Latest decision: {report['latest_decision'] or 'missing'}",
        f"- Evidence status: {report['evidence_status'] or 'missing'}",
    ]
    lines.extend(f"- Action: {action}" for action in report["actions"])
    if report["errors"]:
        lines.extend(["", "Errors:", *(f"- {error}" for error in report["errors"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or close and archive a verified task/cycle record pair.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--task", type=validate_task_id, required=True, help="Task ID to close and archive.")
    parser.add_argument("--month", default="", help="Archive month in YYYY-MM form. Defaults to the current month.")
    parser.add_argument("--write", action="store_true", help="Mark completed and archive. Without this flag, only preview.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    try:
        validate_archive_month(args.month)
    except ValueError as exc:
        parser.error(str(exc))
    root = find_project_root(args.root)
    report = build_close_plan(root, args.task, args.month)
    report["closed"] = False
    report["moved"] = []
    if args.write and report["ready"]:
        report["moved"] = apply_close(root, report)
        report["closed"] = True
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
