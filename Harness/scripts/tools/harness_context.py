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
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./+\-]{2,}|[\uac00-\ud7a3]{2,}")
PATH_FIELD_PATTERN = re.compile(r"^-\s*Path:\s*`([^`]+)`\s*$", re.MULTILINE | re.IGNORECASE)
VERIFY_FIELD_PATTERN = re.compile(r"^-\s*Verify:\s*(?:`([^`]+)`|(.+))$", re.MULTILINE | re.IGNORECASE)
REQUEST_STOP_WORDS = {
    "the", "and", "for", "from", "with", "this", "that", "project", "task", "work", "improve", "fix",
    "update", "change", "please", "harness", "프로젝트", "작업", "개선", "수정", "변경", "해줘", "해주세요",
}


def _request_has_any(request: str, hints: list[str]) -> bool:
    lowered = request.lower()
    return any(hint.lower() in lowered for hint in hints)


def _keywords(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in REQUEST_STOP_WORDS}


def _relevance_score(request: str, text: str) -> int:
    request_words = _keywords(request)
    if not request_words:
        return 0
    lowered = text.lower()
    return sum(2 if word in lowered else 0 for word in request_words) + len(request_words & _keywords(text))


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = ""
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading:
                sections.append((heading, "\n".join(body)))
            heading = line[3:].strip()
            body = []
        elif heading:
            body.append(line)
    if heading:
        sections.append((heading, "\n".join(body)))
    return sections


def _section_routes(root: Path, body: str) -> dict:
    declared_paths = [value.replace("\\", "/").strip() for value in PATH_FIELD_PATTERN.findall(body)]
    existing_paths = [value for value in declared_paths if not any(marker in value for marker in ["<", ">", "*", "?"]) and (root / value).exists()]
    verification = [(quoted or plain).strip() for quoted, plain in VERIFY_FIELD_PATTERN.findall(body)]
    return {"paths": existing_paths, "verification": verification}


def matched_markdown_sections(root: Path, path: Path, request: str, limit: int = 3) -> list[dict]:
    matches: list[dict] = []
    if not path.exists():
        return matches
    for heading, body in _markdown_sections(read_text(path)):
        score = _relevance_score(request, f"{heading}\n{body}")
        if score:
            matches.append({"path": rel(path, root), "section": heading, "score": score, **_section_routes(root, body)})
    matches.sort(key=lambda item: (-item["score"], item["section"]))
    return matches[:limit]


def index_section_reads(root: Path, request: str) -> list[dict]:
    index = index_dir(root)
    candidates: list[Path] = []
    forced_paths: set[Path] = set()
    if _request_has_any(request, API_HINTS):
        candidates.append(index / "api_surface.md")
        forced_paths.add(index / "api_surface.md")
    if _request_has_any(request, VERIFY_HINTS):
        candidates.append(index / "verification_map.md")
        forced_paths.add(index / "verification_map.md")
    if _request_has_any(request, SOURCE_HINTS):
        candidates.append(index / "source_map.json")
        forced_paths.add(index / "source_map.json")
    candidates.append(index / "project_index.md")
    matches: list[dict] = []
    for path in dict.fromkeys(candidates):
        if not path.exists():
            continue
        if path.suffix == ".json":
            if path != index / "project_index.md":
                matches.append({"path": rel(path, root), "section": "", "score": 1})
            continue
        path_matches = matched_markdown_sections(root, path, request)
        matches.extend(path_matches)
        path_match_count = len(path_matches)
        if path in forced_paths and path_match_count == 0:
            matches.append({"path": rel(path, root), "section": "(entire file)", "score": 1, "paths": [], "verification": []})
    matches.sort(key=lambda item: (-item["score"], item["path"], item["section"]))
    return matches[:3]


def index_first_reads(root: Path, request: str) -> list[str]:
    """Backward-compatible path-only view of request-related index reads."""
    return list(dict.fromkeys(item["path"] for item in index_section_reads(root, request)))


def select_next_items(text: str, request: str, all_next: bool = False, limit: int = 3) -> list[str]:
    items = markdown_list_items(text, limit=1000)
    if all_next:
        return items
    if not request.strip():
        return items[:limit]
    scored = [(_relevance_score(request, item), position, item) for position, item in enumerate(items)]
    relevant = [entry for entry in scored if entry[0] > 0]
    relevant.sort(key=lambda entry: entry[1])
    return [item for _, _, item in relevant[:limit]]


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


def build_context(root: Path, request: str = "", task: str = "", all_next: bool = False) -> dict:
    harness = harness_dir(root)
    project = load_json(harness / "config" / "project.json", {}) or {}
    policy = load_json(harness / "config" / "cycle_policy.json", {}) or {}
    docs = load_json(harness / "config" / "docs.json", {}) or {}
    manifest = load_json(harness / "scripts" / "tools" / "tool_manifest.json", {}) or {}
    daily_cycle = today_cycle_path(root)
    active_task = task_path(root, task) if task else None
    active_cycle = task_cycle_path(root, task) if task else None
    index_matches = index_section_reads(root, request)
    index_reads = list(dict.fromkeys(match["path"] for match in index_matches))
    state_matches = matched_markdown_sections(root, state_path(root), request, limit=2)
    selected_next_items = select_next_items(read_text(next_path(root)), request, all_next=all_next)
    first_reads = ["HARNESS.md", "Harness/README.md"]
    if state_matches:
        first_reads.append("Harness/work/state.md")
    if selected_next_items:
        first_reads.append("Harness/work/next.md")
    first_reads.extend(index_reads)
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
        "state_sections": state_matches,
        "next_items": selected_next_items,
        "all_next": all_next,
        "cycle_policy": {"default_max_cycles": policy.get("default_max_cycles", 1), "stop_conditions": policy.get("stop_conditions", []), "request_eval": evaluate_cycle_request(request, policy)},
        "project_docs": {"doc_roots": docs.get("doc_roots", []), "entry_points": docs.get("entry_points", []), "request_eval": evaluate_request(request, docs)},
        "project_index": {"recommended_first_reads": index_reads, "matched_sections": index_matches, "read_policy": "routing_hints_only"},
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
    lines.extend(["", "Read first:", *(f"- {path}" for path in context["recommended_first_reads"])])
    if context["project_index"]["matched_sections"]:
        lines.extend(["", "Relevant index sections:"])
        for item in context["project_index"]["matched_sections"]:
            details = [*(f"Path: {value}" for value in item.get("paths", [])), *(f"Verify: {value}" for value in item.get("verification", []))]
            lines.append(f"- {item['path']} > {item['section']}" + (" | " + " | ".join(details) if details else ""))
    if context["state_sections"]:
        lines.extend(["", "Relevant state sections:"])
        lines.extend(f"- Harness/work/state.md > {item['section']}" for item in context["state_sections"])
    lines.extend(["", "All next items:" if context["all_next"] else "Related next:"])
    lines.extend(f"- {item}" for item in context["next_items"]) if context["next_items"] else lines.append("- No related next items")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a compact Harness context briefing.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Optional user request to evaluate.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Optional active task ID for task-scoped routing.")
    parser.add_argument("--all-next", action="store_true", help="Show every next.md item instead of request-related items only.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    context = build_context(root, args.request, args.task, all_next=args.all_next)
    print_text_or_json(context if args.json else format_text(context), args.json)


if __name__ == "__main__":
    main()
