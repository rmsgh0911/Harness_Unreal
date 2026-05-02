"""Print a compact Harness briefing for the current agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import (
    file_status,
    find_project_root,
    first_heading,
    harness_dir,
    load_json,
    markdown_list_items,
    read_text,
    rel,
    today_cycle_path,
    print_text_or_json,
)


def build_context(root: Path) -> dict:
    harness = harness_dir(root)
    project = load_json(harness / "config" / "project.json", {}) or {}
    cycle_policy = load_json(harness / "config" / "cycle_policy.json", {}) or {}
    manifest = load_json(harness / "scripts" / "tools" / "tool_manifest.json", {}) or {}
    state_text = read_text(harness / "state.md")
    next_text = read_text(harness / "next.md")
    cycle_path = today_cycle_path(root)

    uproject_files = sorted(path.name for path in root.glob("*.uproject"))
    immediate_items = markdown_list_items(next_text, limit=6)

    return {
        "root": str(root),
        "project": {
            "name": project.get("project_name") or (uproject_files[0].removesuffix(".uproject") if len(uproject_files) == 1 else ""),
            "uproject_file": project.get("uproject_file") or (uproject_files[0] if len(uproject_files) == 1 else ""),
            "engine_version": project.get("engine_version", ""),
            "configured": bool(project.get("project_name") and project.get("uproject_file")),
        },
        "files": {
            "HARNESS.md": file_status(root / "HARNESS.md"),
            "AGENTS.md": file_status(root / "AGENTS.md"),
            "CLAUDE.md": file_status(root / "CLAUDE.md"),
            "Harness/state.md": file_status(harness / "state.md"),
            "Harness/next.md": file_status(harness / "next.md"),
            rel(cycle_path, root): file_status(cycle_path),
        },
        "state_heading": first_heading(state_text),
        "next_items": immediate_items,
        "cycle_policy": {
            "default_max_cycles": cycle_policy.get("default_max_cycles", 1),
            "stop_conditions": cycle_policy.get("stop_conditions", []),
            "tool_directory": cycle_policy.get("tool_policy", {}).get("default_tool_directory", "Harness/scripts/tools"),
        },
        "tools": {
            "registered_count": len(manifest.get("tools", [])),
            "registered": [tool.get("name", "") for tool in manifest.get("tools", []) if isinstance(tool, dict)],
            "manifest": file_status(harness / "scripts" / "tools" / "tool_manifest.json"),
        },
        "verification_commands": [
            "python Harness/scripts/tools/harness_doctor.py",
            "python Harness/scripts/tools/harness_scan.py --json",
            "python Harness/scripts/tools/harness_diff_guard.py",
        ],
        "warnings": build_warnings(root, project, cycle_path),
        "recommended_first_reads": [
            "HARNESS.md",
            "Harness/state.md",
            "Harness/next.md",
            rel(cycle_path, root),
        ],
    }


def build_warnings(root: Path, project: dict, cycle_path: Path) -> list[str]:
    warnings: list[str] = []
    if not project.get("project_name") or not project.get("uproject_file"):
        warnings.append("project.json is not fully configured")
    if not cycle_path.exists():
        warnings.append(f"today cycle log is missing: {rel(cycle_path, root)}")
    if (root / ".git").exists():
        warnings.append("git directory exists; use harness_diff_guard.py to check whether git is available")
    return warnings


def format_text(context: dict) -> str:
    lines = [
        "Harness Context",
        f"- Root: {context['root']}",
        f"- Project: {context['project']['name'] or 'not configured'}",
        f"- UProject: {context['project']['uproject_file'] or 'not configured'}",
        f"- Default max cycles: {context['cycle_policy']['default_max_cycles']}",
        f"- Tool directory: {context['cycle_policy']['tool_directory']}",
        f"- Registered tools: {context['tools']['registered_count']}",
    ]
    if context["warnings"]:
        lines.append("- Warnings: " + "; ".join(context["warnings"]))
    lines.extend(["", "Files:"])
    lines.extend(f"- {name}: {status}" for name, status in context["files"].items())
    lines.append("")
    lines.append("Next:")
    if context["next_items"]:
        lines.extend(f"- {item}" for item in context["next_items"])
    else:
        lines.append("- no short next items found")
    lines.append("")
    lines.append("Read first:")
    lines.extend(f"- {path}" for path in context["recommended_first_reads"])
    lines.append("")
    lines.append("Useful checks:")
    lines.extend(f"- {command}" for command in context["verification_commands"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a compact Harness context briefing.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    context = build_context(root)
    print_text_or_json(context if args.json else format_text(context), args.json)


if __name__ == "__main__":
    main()
