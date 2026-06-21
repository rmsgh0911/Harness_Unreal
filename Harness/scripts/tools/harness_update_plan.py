"""Plan a reviewed Harness template update without overwriting project-owned data."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, rel
from harness_migration_audit import audit
from harness_release_pack import collect_files


PROJECT_OWNED_PREFIXES = (
    "Harness/config/project.json",
    "Harness/config/docs.json",
    "Harness/docs/",
    "Harness/index/",
    "Harness/work/",
    "Harness/Progress.md",
)
MERGE_REVIEW_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "HARNESS.md",
    "INSTALL.md",
    ".gitattributes",
    ".gitignore",
    "Harness/README.md",
    "Harness/config/agents.json",
    "Harness/config/cycle_policy.json",
}


def _is_project_owned(relative: str) -> bool:
    return any(relative == prefix.rstrip("/") or relative.startswith(prefix) for prefix in PROJECT_OWNED_PREFIXES)


def _same_bytes(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.read_bytes() == right.read_bytes()


def build_update_plan(template: Path, target: Path) -> dict:
    template = template.resolve()
    target = target.resolve()
    actions: list[dict] = []
    template_files = collect_files(template)
    template_relatives = {rel(path, template) for path in template_files}
    for source in template_files:
        relative = rel(source, template)
        destination = target / relative
        if _is_project_owned(relative):
            action = "preserve" if destination.exists() else "initialize_missing"
            reason = "project_owned" if destination.exists() else "missing_project_owned_template"
        elif relative in MERGE_REVIEW_PATHS:
            action = "add" if not destination.exists() else ("unchanged" if _same_bytes(source, destination) else "merge_review")
            reason = "shared_policy_or_repository_rules"
        else:
            action = "add" if not destination.exists() else ("unchanged" if _same_bytes(source, destination) else "replace_review")
            reason = "standard_template_file"
        actions.append({"path": relative, "action": action, "reason": reason})

    custom_tools: list[str] = []
    target_scripts = target / "Harness" / "scripts"
    if target_scripts.exists():
        for path in sorted(target_scripts.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = rel(path, target)
            if relative not in template_relatives:
                custom_tools.append(relative)

    counts: dict[str, int] = {}
    for item in actions:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    migration = audit(target)
    return {
        "template": str(template),
        "target": str(target),
        "same_root": template == target,
        "layout": migration["layout"],
        "counts": counts,
        "actions": actions,
        "custom_tools": custom_tools,
        "preserve": migration["preserve"],
        "cleanup_after_verification": migration["cleanup"],
        "recommended_sequence": [
            "commit or back up the target project before applying additions",
            "apply only missing files, then review staged merge/replace candidates",
            "preserve project-owned config, docs, index, work records, Progress, and custom tools",
            "run harness_knowledge.py to reuse existing Harness material",
            "run harness_verify_all.py and inspect git diff --stat before removing legacy paths",
        ],
    }


def apply_missing_files(template: Path, target: Path, plan: dict) -> list[str]:
    if template.resolve() == target.resolve():
        raise ValueError("template and target must differ when applying files")
    copied: list[str] = []
    for item in plan["actions"]:
        if item["action"] not in {"add", "initialize_missing"}:
            continue
        source = template / item["path"]
        destination = target / item["path"]
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(item["path"])
    return copied


def stage_review_files(template: Path, stage: Path, plan: dict) -> list[str]:
    staged: list[str] = []
    for item in plan["actions"]:
        if item["action"] not in {"merge_review", "replace_review"}:
            continue
        source = template / item["path"]
        destination = stage / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged.append(item["path"])
    return staged


def format_text(report: dict) -> str:
    lines = [
        "Harness Update Plan",
        f"- Template: {report['template']}",
        f"- Target: {report['target']}",
        f"- Target layout: {report['layout']['kind']}",
        f"- Custom tools preserved: {len(report['custom_tools'])}",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(report["counts"].items()))
    for title, actions in [
        ("Merge Review", {"merge_review"}),
        ("Replace Review", {"replace_review"}),
        ("Preserved Project Data", {"preserve"}),
    ]:
        selected = [item["path"] for item in report["actions"] if item["action"] in actions]
        lines.extend(["", f"{title}:"])
        lines.extend(f"- {item}" for item in selected[:30]) if selected else lines.append("- none")
    if report["custom_tools"]:
        lines.extend(["", "Custom Tools:", *(f"- {item}" for item in report["custom_tools"])])
    lines.extend(["", "Recommended Sequence:", *(f"- {item}" for item in report["recommended_sequence"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a new Harness template with an older target install.")
    parser.add_argument("--template", type=Path, default=None, help="New template root. Defaults to the current Harness template root.")
    parser.add_argument("--target", type=Path, required=True, help="Older project root to update.")
    parser.add_argument("--apply-missing", action="store_true", help="Copy only files that do not exist in the target. Never overwrites.")
    parser.add_argument("--stage-review", type=Path, default=None, help="Copy merge/replace candidates into this separate review directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    template = find_project_root(args.template).resolve()
    target = args.target.resolve()
    if args.stage_review:
        stage = args.stage_review.resolve()
        if stage in {template, target}:
            parser.error("--stage-review must be a separate directory, not the template or target root")
    report = build_update_plan(template, target)
    report["copied_missing"] = apply_missing_files(template, target, report) if args.apply_missing else []
    report["staged_review"] = stage_review_files(template, stage, report) if args.stage_review else []
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
