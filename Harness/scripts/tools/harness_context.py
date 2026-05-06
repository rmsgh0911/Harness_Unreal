"""Print a compact Harness briefing for the current agent."""

from __future__ import annotations

import argparse
import re
import shutil
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
from harness_docs_check import evaluate_request


KOREAN_CYCLE = "\uc0ac\uc774\ud074"
KOREAN_ITERATE = "\ubc18\ubcf5"
KOREAN_MAX = "\ucd5c\ub300"


def _context_check_commands(manifest: dict) -> list[str]:
    """Return verify commands for tools flagged with context_check: true."""
    tools = manifest.get("tools", []) if isinstance(manifest, dict) else []
    return [
        tool["verify"]
        for tool in tools
        if isinstance(tool, dict) and tool.get("context_check") and tool.get("verify")
    ]


def evaluate_cycle_request(request: str, cycle_policy: dict) -> dict:
    request_text = request.strip()
    if not request_text:
        return {
            "request": "",
            "is_cycle_work": False,
            "max_cycles": cycle_policy.get("default_max_cycles", 1),
            "reason": "no request provided",
        }

    lowered = request_text.lower()
    phrases = cycle_policy.get("cycle_count_rules", {}).get("phrases", [])
    phrase_hits = [phrase for phrase in phrases if isinstance(phrase, str) and phrase.lower() in lowered]
    cycle_words = ["cycle", "cycles", "iterate", KOREAN_CYCLE, KOREAN_ITERATE]
    word_hits = [word for word in cycle_words if word.lower() in lowered]
    max_cycles = None
    patterns = [
        rf"{KOREAN_MAX}\s*(\d+)\s*(?:\ud68c|{KOREAN_CYCLE})",
        r"up to\s*(\d+)\s*(?:times|cycles?)",
        r"max(?:imum)?\s*(\d+)\s*(?:times|cycles?)",
        r"(\d+)\s*cycles?",
        rf"(\d+)\s*{KOREAN_CYCLE}",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            max_cycles = int(match.group(1))
            break
    hits = list(dict.fromkeys([*phrase_hits, *word_hits]))
    is_cycle_work = bool(hits or max_cycles)
    return {
        "request": request_text,
        "is_cycle_work": is_cycle_work,
        "max_cycles": max_cycles if max_cycles is not None else cycle_policy.get("default_max_cycles", 1),
        "max_cycles_is_upper_bound": cycle_policy.get("cycle_count_rules", {}).get("max_cycles_is_upper_bound", True),
        "stop_before_max_when_success_criteria_met": cycle_policy.get("cycle_count_rules", {}).get(
            "stop_before_max_when_success_criteria_met", True
        ),
        "reason": "matched cycle request hints" if is_cycle_work else "no cycle trigger matched",
        "hits": hits,
    }


def build_context(root: Path, request: str = "") -> dict:
    harness = harness_dir(root)
    project = load_json(harness / "config" / "project.json", {}) or {}
    cycle_policy = load_json(harness / "config" / "cycle_policy.json", {}) or {}
    docs_config = load_json(harness / "config" / "docs.json", {}) or {}
    manifest = load_json(harness / "scripts" / "tools" / "tool_manifest.json", {}) or {}
    state_text = read_text(harness / "state.md")
    next_text = read_text(harness / "next.md")
    cycle_path = today_cycle_path(root)
    project_configured = bool(project.get("project_name") and project.get("uproject_file"))
    recommended_first_reads = [
        "HARNESS.md",
        "Harness/state.md",
        "Harness/next.md",
    ]
    if cycle_path.exists():
        recommended_first_reads.append(rel(cycle_path, root))

    uproject_files = sorted(path.name for path in root.glob("*.uproject"))
    immediate_items = markdown_list_items(next_text, limit=6)
    request_eval = evaluate_request(request, docs_config)
    cycle_eval = evaluate_cycle_request(request, cycle_policy)
    files = {
        "HARNESS.md": file_status(root / "HARNESS.md"),
        "AGENTS.md": file_status(root / "AGENTS.md"),
        "CLAUDE.md": file_status(root / "CLAUDE.md"),
        "Harness/state.md": file_status(harness / "state.md"),
        "Harness/next.md": file_status(harness / "next.md"),
    }
    if project_configured or cycle_path.exists():
        files[rel(cycle_path, root)] = file_status(cycle_path)

    return {
        "root": str(root),
        "project": {
            "name": project.get("project_name") or (uproject_files[0].removesuffix(".uproject") if len(uproject_files) == 1 else ""),
            "uproject_file": project.get("uproject_file") or (uproject_files[0] if len(uproject_files) == 1 else ""),
            "engine_version": project.get("engine_version", ""),
            "configured": project_configured,
        },
        "files": files,
        "state_heading": first_heading(state_text),
        "next_items": immediate_items,
        "cycle_policy": {
            "default_max_cycles": cycle_policy.get("default_max_cycles", 1),
            "stop_conditions": cycle_policy.get("stop_conditions", []),
            "tool_directory": cycle_policy.get("tool_policy", {}).get("default_tool_directory", "Harness/scripts/tools"),
            "request_eval": cycle_eval,
        },
        "project_docs": {
            "doc_roots": docs_config.get("doc_roots", []),
            "entry_points": docs_config.get("entry_points", []),
            "optional_external_roots": docs_config.get("optional_external_roots", []),
            "read_policy": docs_config.get("read_policy", {}).get("default", "on_demand"),
            "request_eval": request_eval,
        },
        "tools": {
            "registered_count": len(manifest.get("tools", [])),
            "registered": [tool.get("name", "") for tool in manifest.get("tools", []) if isinstance(tool, dict)],
            "manifest": file_status(harness / "scripts" / "tools" / "tool_manifest.json"),
        },
        "verification_commands": _context_check_commands(manifest),
        "warnings": build_warnings(root, project, cycle_path),
        "recommended_first_reads": recommended_first_reads,
    }


def build_warnings(root: Path, project: dict, cycle_path: Path) -> list[str]:
    warnings: list[str] = []
    project_configured = bool(project.get("project_name") and project.get("uproject_file"))
    if not project_configured:
        warnings.append("project.json is not fully configured")
    if project_configured and not cycle_path.exists():
        warnings.append(f"today cycle log is missing: {rel(cycle_path, root)}")
    if (root / ".git").exists() and not shutil.which("git"):
        warnings.append("git repository found but git CLI not in PATH; change tracking will be limited (harness_diff_guard.py will use directory scan mode)")
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
    if context["project_docs"]["doc_roots"]:
        lines.append("- Project docs: " + ", ".join(context["project_docs"]["doc_roots"]))
    if context["project_docs"]["optional_external_roots"]:
        lines.append("- Optional external docs: " + ", ".join(context["project_docs"]["optional_external_roots"]))
    request_eval = context["project_docs"].get("request_eval", {})
    if request_eval.get("request"):
        lines.append(f"- Should read docs: {request_eval.get('should_read_docs')}")
        if request_eval.get("recommended_first_reads"):
            lines.append("- Docs first reads: " + ", ".join(request_eval["recommended_first_reads"]))
    cycle_eval = context["cycle_policy"].get("request_eval", {})
    if cycle_eval.get("request"):
        lines.append(f"- Cycle work: {cycle_eval.get('is_cycle_work')}")
        if cycle_eval.get("is_cycle_work"):
            lines.append(f"- Max cycles: {cycle_eval.get('max_cycles')} (upper bound)")
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
    parser.add_argument("--request", default="", help="Optional user request to evaluate against docs.json.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    context = build_context(root, args.request)
    print_text_or_json(context if args.json else format_text(context), args.json)


if __name__ == "__main__":
    main()
