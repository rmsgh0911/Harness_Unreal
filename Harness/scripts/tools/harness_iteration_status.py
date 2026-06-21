"""Report progress, budget, and convergence signals for repeated Harness work."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, load_json, rel, task_cycle_path, today_cycle_path, validate_task_id
from harness_context import evaluate_cycle_request
from harness_cycle_summary import parse_cycle_file


def _remaining_signature(section: dict) -> tuple[str, ...]:
    ignored = {"", "none", "record needed"}
    return tuple(value.strip().casefold() for value in section.get("remaining", []) if value.strip().casefold() not in ignored)


def build_status(root: Path, request: str = "", task: str = "") -> dict:
    policy = load_json(root / "Harness" / "config" / "cycle_policy.json", {}) or {}
    request_eval = evaluate_cycle_request(request, policy)
    path = task_cycle_path(root, task) if task else today_cycle_path(root)
    parsed = parse_cycle_file(path) if path.exists() else {"sections": [], "iteration": {"warnings": []}}
    sections = parsed["sections"]
    latest = sections[-1] if sections else None
    recorded_budget = next((section["max_cycles"] for section in reversed(sections) if section.get("max_cycles")), None)
    budget = recorded_budget or request_eval["max_cycles"]
    repeated_remaining = False
    if len(sections) >= 2:
        latest_signature = _remaining_signature(sections[-1])
        repeated_remaining = bool(latest_signature and latest_signature == _remaining_signature(sections[-2]))
    verification_gaps = sum(
        1 for section in sections
        if not [value for value in section.get("verified", []) if value not in {"", "record needed"}]
    )
    stop_reasons: list[str] = []
    if latest and latest.get("decision") in {"stop_success", "stop_blocked"}:
        stop_reasons.append(f"latest_decision:{latest['decision']}")
    if budget and len(sections) >= budget:
        stop_reasons.append("cycle_budget_exhausted")
    if repeated_remaining:
        stop_reasons.append("same_remaining_repeated_twice")
    stop_reasons.extend(f"invalid_cycle_log:{warning}" for warning in parsed["iteration"]["warnings"])
    return {
        "root": str(root),
        "task": task,
        "cycle_path": rel(path, root),
        "cycle_file_exists": path.exists(),
        "completed_cycles": len(sections),
        "budget": budget,
        "budget_mode": request_eval["budget_mode"],
        "remaining_cycles": max(budget - len(sections), 0) if budget else None,
        "next_cycle": len(sections) + 1,
        "latest_decision": latest.get("decision", "") if latest else "",
        "repeated_remaining": repeated_remaining,
        "verification_gaps": verification_gaps,
        "cycle_log_warnings": parsed["iteration"]["warnings"],
        "stop_reasons": stop_reasons,
        "continue_recommended": not stop_reasons,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Iteration Status",
        f"- Root: {report['root']}",
        f"- Task: {report['task'] or 'daily cycle'}",
        f"- Cycle file: {report['cycle_path']}",
        f"- Progress: {report['completed_cycles']}/{report['budget']}",
        f"- Remaining budget: {report['remaining_cycles']}",
        f"- Latest decision: {report['latest_decision'] or 'not recorded'}",
        f"- Verification gaps: {report['verification_gaps']}",
        f"- Continue recommended: {report['continue_recommended']}",
    ]
    if report["stop_reasons"]:
        lines.extend(["", "Stop reasons:", *(f"- {reason}" for reason in report["stop_reasons"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report iteration budget, progress, and convergence signals.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Original repeated-work request used to infer the budget.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Optional task ID selecting a task-scoped cycle file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    report = build_status(root, request=args.request, task=args.task)
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
