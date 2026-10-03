"""Build a compact handoff brief for another agent or session."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, read_text, rel, task_cycle_path, today_cycle_path, validate_task_id, write_text
from harness_common import require_owned_path
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
    warnings = list(context.get("warnings", []))
    if not diff["change_list_reliable"]:
        warnings.append("Git change inventory is unknown (CLI unavailable, query failed, or root mismatch); limited scan is not a clean-tree verdict.")
    if warnings:
        lines.extend(["", "## Evidence Warnings", *(f"- {item}" for item in warnings[:20])])
        if len(warnings) > 20:
            lines.append(f"- Omitted warnings: {len(warnings) - 20}")
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
    if diff["change_list_reliable"]:
        groups = {"Staged": [], "Unstaged": [], "Untracked": []}
        for item in diff["changed"]:
            name = json.dumps(changed_path_from_status(item), ensure_ascii=False)
            if item.startswith("??"):
                groups["Untracked"].append(name)
            else:
                if item[0] != " ":
                    groups["Staged"].append(name)
                if item[1] != " ":
                    groups["Unstaged"].append(name)
        for label, names in groups.items():
            lines.append(f"### {label}: {len(names)}")
            lines.extend(f"- {name}" for name in names[:40])
            if len(names) > 40:
                lines.append(f"- Omitted paths: {len(names) - 40}; refresh a scoped status packet before acting.")
            if not names:
                lines.append("- none detected")
    else:
        lines.append("- unknown; ordinary staged/unstaged/untracked changes could not be inspected")
    lines.extend(["", "## Risk Signals"])
    if diff["risks"]:
        lines.extend(f"- [{item['level']}] {json.dumps(item['path'], ensure_ascii=False)}: {item['reason']}" for item in diff["risks"][:40])
        if len(diff["risks"]) > 40:
            lines.append(f"- Omitted risk signals: {len(diff['risks']) - 40}")
    else:
        lines.append("- none detected" if diff["change_list_reliable"] else "- unknown outside the limited scan")
    lines.extend(["", f"## Cycle Tail: {rel(cycle_path, root)}"])
    lines.extend(tail_lines(cycle_text) or ["- no active cycle log"])
    if len(cycle_text.splitlines()) > 30:
        lines.append(f"- Earlier cycle lines omitted: {len(cycle_text.splitlines()) - 30}; read the cycle record before retrying or closing.")
    return "\n".join(lines) + "\n"


def write_handoff(root: Path, output: Path, text: str) -> Path:
    output = output if output.is_absolute() else root / output
    require_owned_path(root, output)
    if output.exists() and not read_text(output).startswith("# Harness Handoff\n"):
        raise ValueError("refusing to overwrite a file that is not a generated Harness handoff")
    write_text(output, text)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact Harness handoff brief.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Current user request or handoff reason.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Optional active task ID.")
    parser.add_argument("--output", type=Path, default=None, help="Project-relative output path. Defaults to Harness/handoff.md; only generated handoffs may be replaced.")
    parser.add_argument("--write", action="store_true", help="Write the handoff brief. Default is dry run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    output = args.output or (root / "Harness" / "handoff.md")
    if not output.is_absolute():
        output = root / output
    try:
        text = build_handoff(root, args.request, args.task)
        if args.write:
            write_handoff(root, output, text)
    except (OSError, ValueError) as exc:
        print(dump_json({"ok": False, "status": "failed", "error": str(exc)}))
        raise SystemExit(1)
    result = {"root": str(root), "output": rel(output, root), "write": args.write, "status": "written" if args.write else "dry_run", "handoff": text}
    if args.json:
        print(dump_json(result))
    elif args.write:
        print(f"Wrote handoff brief: {output}")
    else:
        print(text.rstrip())
        print(f"\nDry run only. Add --write to write {output}")


if __name__ == "__main__":
    main()
