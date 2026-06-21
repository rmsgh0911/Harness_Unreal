"""Build a compact handoff brief for another agent or session."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, read_text, rel, task_cycle_path, today_cycle_path, validate_task_id, write_text
from harness_context import build_context
from harness_diff_guard import build_report, changed_path_from_status


def tail_lines(text: str, limit: int = 30) -> list[str]:
    return [line.rstrip() for line in text.splitlines()][-limit:]


def build_handoff(root: Path, request: str = "", task: str = "") -> str:
    context = build_context(root, request=request, task=task)
    diff = build_report(root)
    cycle_path = task_cycle_path(root, task) if task else today_cycle_path(root)
    cycle_text = read_text(cycle_path)
    next_items = context["next_items"]
    iteration = context["cycle_policy"].get("iteration_status")
    lines = [
        "# Harness Handoff",
        "",
        f"- Created: {datetime.now().astimezone().isoformat(timespec='minutes')}",
        f"- Root: {root}",
        f"- Request: {request or 'not recorded'}",
        f"- Task: {task or 'not recorded'}",
        f"- Project: {context['project']['name'] or 'not configured'}",
        f"- uproject: {context['project']['uproject_file'] or 'not configured'}",
        f"- Git available: {diff['git_available']}",
        f"- Changed files: {diff['changed_count'] if diff['change_list_reliable'] else 'limited detection'}",
        f"- Risk signals: {diff['risk_count']}",
        "",
        "## Read First",
    ]
    lines.extend(f"- {item}" for item in context["recommended_first_reads"])
    if iteration:
        lines.extend([
            "",
            "## Iteration",
            f"- Progress: {iteration['completed_cycles']}/{iteration['budget']}",
            f"- Remaining budget: {iteration['remaining_cycles']}",
            f"- Latest decision: {iteration['latest_decision'] or 'not recorded'}",
            f"- Continue recommended: {iteration['continue_recommended']}",
        ])
    lines.extend(["", "## Next Work"])
    lines.extend(f"- {item}" for item in next_items or ["No related next items"])
    lines.extend(["", "## Changed Files"])
    lines.extend(f"- {changed_path_from_status(item)}" for item in diff["changed"][:40]) if diff["changed"] else lines.append("- none detected")
    lines.extend(["", "## Risk Signals"])
    lines.extend(f"- [{item['level']}] {item['path']}: {item['reason']}" for item in diff["risks"]) if diff["risks"] else lines.append("- none")
    lines.extend(["", f"## Cycle Tail: {rel(cycle_path, root)}"])
    lines.extend(tail_lines(cycle_text) or ["- no active cycle log"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact Harness handoff brief.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Current user request or handoff reason.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Optional active task ID.")
    parser.add_argument("--output", type=Path, default=None, help="Output path. Defaults to Harness/handoff.md.")
    parser.add_argument("--write", action="store_true", help="Write the handoff brief. Default is dry run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    output = args.output or (root / "Harness" / "handoff.md")
    text = build_handoff(root, args.request, args.task)
    result = {"root": str(root), "output": rel(output, root), "write": args.write, "status": "written" if args.write else "dry_run", "handoff": text}
    if args.write:
        write_text(output, text)
    if args.json:
        print(dump_json(result))
    elif args.write:
        print(f"Wrote handoff brief: {output}")
    else:
        print(text.rstrip())
        print(f"\nDry run only. Add --write to write {output}")


if __name__ == "__main__":
    main()
