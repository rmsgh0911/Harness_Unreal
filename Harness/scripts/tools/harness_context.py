"""Print a compact Harness briefing for the current agent."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import file_status, find_project_root, first_heading, harness_dir, index_dir, load_json, markdown_list_items, next_path, print_text_or_json, read_text, rel, state_path, task_cycle_path, task_path, today_cycle_path, validate_task_id
from harness_docs_check import evaluate_request

KOREAN_CYCLE = "\uc0ac\uc774\ud074"
KOREAN_ITERATE = "\ubc18\ubcf5"
KOREAN_MAX = "\ucd5c\ub300"
API_HINTS = ["api", "blueprint", "ufunction", "uproperty", "mqtt", "topic", "json", "payload", "route", "signature"]
VERIFY_HINTS = ["verify", "verification", "build", "compile", "test", "pie", "\uac80\uc99d", "\ube4c\ub4dc", "\ucef4\ud30c\uc77c"]
SOURCE_HINTS = ["source", "module", "class", "c++", "cpp", "header", "\uc18c\uc2a4", "\ubaa8\ub4c8", "\ud074\ub798\uc2a4"]


def _request_has_any(request: str, hints: list[str]) -> bool:
    lowered = request.lower()
    return any(hint.lower() in lowered for hint in hints)


def index_first_reads(root: Path, request: str) -> list[str]:
    index = index_dir(root)
    candidates = [index / "project_index.md"]
    if _request_has_any(request, API_HINTS):
        candidates.append(index / "api_surface.md")
    if _request_has_any(request, VERIFY_HINTS):
        candidates.append(index / "verification_map.md")
    if _request_has_any(request, SOURCE_HINTS):
        candidates.append(index / "source_map.json")
    return [rel(path, root) for path in candidates if path.exists()]


def evaluate_cycle_request(request: str, policy: dict) -> dict:
    request_text = request.strip()
    default = policy.get("default_max_cycles", 1)
    if not request_text:
        return {"request": "", "is_cycle_work": False, "max_cycles": default, "reason": "no request provided"}
    lowered = request_text.lower()
    phrases = policy.get("cycle_count_rules", {}).get("phrases", [])
    hits = [phrase for phrase in phrases if isinstance(phrase, str) and phrase.lower() in lowered]
    hits.extend(word for word in ["cycle", "cycles", "iterate", KOREAN_CYCLE, KOREAN_ITERATE] if word.lower() in lowered)
    maximum = None
    for pattern in [
        rf"{KOREAN_MAX}\s*(\d+)\s*(?:\ud68c|{KOREAN_CYCLE})",
        r"up to\s*(\d+)\s*(?:times|cycles?)",
        r"max(?:imum)?\s*(\d+)\s*(?:times|cycles?)",
        r"(\d+)\s*cycles?",
        rf"(\d+)\s*{KOREAN_CYCLE}",
    ]:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            maximum = int(match.group(1))
            break
    is_cycle = bool(hits or maximum)
    return {
        "request": request_text,
        "is_cycle_work": is_cycle,
        "max_cycles": maximum if maximum is not None else default,
        "max_cycles_is_upper_bound": True,
        "stop_before_max_when_success_criteria_met": True,
        "reason": "matched cycle request hints" if is_cycle else "no cycle trigger matched",
        "hits": list(dict.fromkeys(hits)),
    }


def build_context(root: Path, request: str = "", task: str = "") -> dict:
    harness = harness_dir(root)
    project = load_json(harness / "config" / "project.json", {}) or {}
    policy = load_json(harness / "config" / "cycle_policy.json", {}) or {}
    docs = load_json(harness / "config" / "docs.json", {}) or {}
    manifest = load_json(harness / "scripts" / "tools" / "tool_manifest.json", {}) or {}
    daily_cycle = today_cycle_path(root)
    active_task = task_path(root, task) if task else None
    active_cycle = task_cycle_path(root, task) if task else None
    index_reads = index_first_reads(root, request)
    first_reads = ["HARNESS.md", "Harness/work/state.md", "Harness/work/next.md", *index_reads]
    if active_task and active_task.exists():
        first_reads.append(rel(active_task, root))
    if active_cycle and active_cycle.exists():
        first_reads.append(rel(active_cycle, root))
    elif daily_cycle.exists():
        first_reads.append(rel(daily_cycle, root))
    first_reads = list(dict.fromkeys(first_reads))

    files = {
        "HARNESS.md": file_status(root / "HARNESS.md"),
        "AGENTS.md": file_status(root / "AGENTS.md"),
        "CLAUDE.md": file_status(root / "CLAUDE.md"),
        "Harness/work/state.md": file_status(state_path(root)),
        "Harness/work/next.md": file_status(next_path(root)),
        "Harness/index/project_index.md": file_status(index_dir(root) / "project_index.md"),
    }
    if active_task:
        files[rel(active_task, root)] = file_status(active_task)
    if active_cycle:
        files[rel(active_cycle, root)] = file_status(active_cycle)

    warnings: list[str] = []
    configured = bool(project.get("project_name") and project.get("uproject_file"))
    if not configured and not project.get("template_mode", False):
        warnings.append("project.json is not fully configured")
    if active_task and not active_task.exists():
        warnings.append(f"task record is missing: {rel(active_task, root)}")
    if active_task and active_task.exists() and active_cycle and not active_cycle.exists():
        warnings.append(f"task cycle log is missing: {rel(active_cycle, root)}")
    if (root / ".git").exists() and not shutil.which("git"):
        warnings.append("git repository found but git CLI is not in PATH")

    uprojects = sorted(path.name for path in root.glob("*.uproject"))
    tools = [tool for tool in manifest.get("tools", []) if isinstance(tool, dict)]
    return {
        "root": str(root),
        "active_task": task,
        "project": {
            "name": project.get("project_name") or (uprojects[0].removesuffix(".uproject") if len(uprojects) == 1 else ""),
            "uproject_file": project.get("uproject_file") or (uprojects[0] if len(uprojects) == 1 else ""),
            "engine_version": project.get("engine_version", ""),
            "configured": configured,
            "template_mode": bool(project.get("template_mode", False)),
        },
        "files": files,
        "state_heading": first_heading(read_text(state_path(root))),
        "next_items": markdown_list_items(read_text(next_path(root)), limit=6),
        "cycle_policy": {"default_max_cycles": policy.get("default_max_cycles", 1), "stop_conditions": policy.get("stop_conditions", []), "request_eval": evaluate_cycle_request(request, policy)},
        "project_docs": {"doc_roots": docs.get("doc_roots", []), "entry_points": docs.get("entry_points", []), "request_eval": evaluate_request(request, docs)},
        "project_index": {"recommended_first_reads": index_reads, "read_policy": "routing_hints_only"},
        "tools": {"registered_count": len(tools), "registered": [tool.get("name", "") for tool in tools], "manifest": file_status(harness / "scripts" / "tools" / "tool_manifest.json")},
        "verification_commands": [tool["verify"] for tool in tools if tool.get("context_check") and tool.get("verify")],
        "warnings": warnings,
        "recommended_first_reads": first_reads,
    }


def format_text(context: dict) -> str:
    lines = [
        "Harness Context",
        f"- Root: {context['root']}",
        f"- Project: {context['project']['name'] or 'not configured'}",
        f"- Active task: {context['active_task'] or 'not specified'}",
        f"- Template mode: {context['project']['template_mode']}",
        f"- Registered tools: {context['tools']['registered_count']}",
    ]
    if context["warnings"]:
        lines.append("- Warnings: " + "; ".join(context["warnings"]))
    lines.extend(["", "Read first:", *(f"- {path}" for path in context["recommended_first_reads"]), "", "Next:"])
    lines.extend(f"- {item}" for item in context["next_items"]) if context["next_items"] else lines.append("- no short next items found")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a compact Harness context briefing.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Optional user request to evaluate.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Optional active task ID for task-scoped routing.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    context = build_context(root, args.request, args.task)
    print_text_or_json(context if args.json else format_text(context), args.json)


if __name__ == "__main__":
    main()
