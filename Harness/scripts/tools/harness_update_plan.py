"""Plan a reviewed Harness template update without overwriting project-owned data."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, rel
from harness_migration_audit import audit
from harness_release_pack import collect_files


PROJECT_OWNED_FILES = {
    "Harness/config/project.json",
    "Harness/config/docs.json",
    "Harness/Progress.md",
}
PROJECT_OWNED_PREFIXES = (
    "Harness/docs/",
    "Harness/index/",
    "Harness/work/",
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
    return relative in PROJECT_OWNED_FILES or any(relative == prefix.rstrip("/") or relative.startswith(prefix) for prefix in PROJECT_OWNED_PREFIXES)


def _same_bytes(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.read_bytes() == right.read_bytes()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _planned_paths(base: Path, relative: str) -> tuple[Path, Path]:
    """Validate a plan path and return its lexical and resolved forms."""
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or candidate == Path(".") or ".." in candidate.parts:
        raise ValueError(f"unsafe planned path: {relative!r}")
    lexical = base / candidate
    resolved = lexical.resolve()
    if not _is_within(resolved, base):
        raise ValueError(f"planned path escapes its root: {relative!r}")
    return lexical, resolved


def validate_template_root(template: Path) -> list[Path]:
    if not template.is_dir() or not (template / "HARNESS.md").is_file() or not (template / "Harness").is_dir():
        raise ValueError("template must be an existing Harness template root containing HARNESS.md and Harness/")
    files = collect_files(template)
    if not files:
        raise ValueError("template contains no releasable Harness files")
    return files


def build_update_plan(template: Path, target: Path) -> dict:
    template = template.resolve()
    target = target.resolve()
    actions: list[dict] = []
    template_files = validate_template_root(template)
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
    if not target.is_dir() or not (target / "Harness").is_dir():
        raise ValueError("target must be an existing project with a Harness directory; use the normal initialization flow for a new project")
    operations: list[tuple[str, Path, Path]] = []
    for item in plan["actions"]:
        if item["action"] not in {"add", "initialize_missing"}:
            continue
        source, resolved_source = _planned_paths(template, item["path"])
        destination, _ = _planned_paths(target, item["path"])
        if destination.exists():
            continue
        if not source.is_file() or not _is_within(resolved_source, template):
            raise FileNotFoundError(f"planned template source is missing: {source}")
        operations.append((item["path"], source, destination))

    promoted: list[Path] = []
    created_dirs: set[Path] = set()
    try:
        with tempfile.TemporaryDirectory(prefix=".harness-update-", dir=target) as temp_dir:
            staging = Path(temp_dir)
            staged_operations: list[tuple[str, Path, Path]] = []
            for relative, source, destination in operations:
                staged = staging / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, staged)
                staged_operations.append((relative, staged, destination))
            for _, staged, destination in staged_operations:
                cursor = destination.parent
                while not cursor.exists() and cursor != target.parent:
                    created_dirs.add(cursor)
                    cursor = cursor.parent
                destination.parent.mkdir(parents=True, exist_ok=True)
                with staged.open("rb") as source_stream, destination.open("xb") as destination_stream:
                    promoted.append(destination)
                    shutil.copyfileobj(source_stream, destination_stream)
                shutil.copystat(staged, destination)
    except Exception:
        for destination in reversed(promoted):
            if destination.exists():
                destination.unlink()
        for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    pass
        raise
    return [relative for relative, _, _ in operations]


def stage_review_files(template: Path, stage: Path, plan: dict, overwrite: bool = False, target: Path | None = None) -> list[str]:
    if _is_within(stage, template) or (target is not None and _is_within(stage, target)):
        raise ValueError("review staging directory must be outside both the template and target trees")
    candidates = [item for item in plan["actions"] if item["action"] in {"merge_review", "replace_review"}]
    destinations = {item["path"]: _planned_paths(stage, item["path"])[0] for item in candidates}
    existing = [str(destinations[item["path"]].resolve()) for item in candidates if destinations[item["path"]].exists()]
    if existing and not overwrite:
        raise FileExistsError("review staging files already exist; choose an empty directory or pass --overwrite-stage: " + ", ".join(existing[:5]))
    operations: list[tuple[str, Path, Path]] = []
    for item in candidates:
        source, resolved_source = _planned_paths(template, item["path"])
        destination = destinations[item["path"]]
        if not source.is_file() or not _is_within(resolved_source, template):
            raise FileNotFoundError(f"planned review source is missing: {source}")
        operations.append((item["path"], source, destination))

    stage_parent_existed = stage.parent.exists()
    stage.parent.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []
    backups: dict[Path, Path] = {}
    created_dirs: set[Path] = set()
    temporary_context = tempfile.TemporaryDirectory(prefix=".harness-review-", dir=stage.parent)
    temporary = Path(temporary_context.name)
    try:
        prepared: list[tuple[str, Path, Path]] = []
        for relative, source, destination in operations:
            staged_source = temporary / "new" / relative
            staged_source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged_source)
            if destination.exists():
                backup = temporary / "backup" / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup)
                backups[destination] = backup
            prepared.append((relative, staged_source, destination))
        for _, staged_source, destination in prepared:
            cursor = destination.parent
            while not cursor.exists() and cursor != stage.parent.parent:
                created_dirs.add(cursor)
                cursor = cursor.parent
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.copy2(staged_source, destination)
            else:
                with staged_source.open("rb") as source_stream, destination.open("xb") as destination_stream:
                    shutil.copyfileobj(source_stream, destination_stream)
                shutil.copystat(staged_source, destination)
            changed.append(destination)
    except Exception:
        for destination in reversed(changed):
            backup = backups.get(destination)
            if backup and backup.exists():
                shutil.copy2(backup, destination)
            elif destination.exists():
                destination.unlink()
        for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    pass
        if not stage_parent_existed and stage.parent.exists():
            try:
                stage.parent.rmdir()
            except OSError:
                pass
        raise
    finally:
        temporary_context.cleanup()
    return [relative for relative, _, _ in operations]


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
        if selected:
            lines.extend(f"- {item}" for item in selected[:30])
        else:
            lines.append("- none")
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
    parser.add_argument("--overwrite-stage", action="store_true", help="Allow --stage-review to replace files already present in the review directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if args.overwrite_stage and not args.stage_review:
        parser.error("--overwrite-stage requires --stage-review")
    template = find_project_root(args.template).resolve()
    target = args.target.resolve()
    if args.stage_review:
        stage = args.stage_review.resolve()
        if _is_within(stage, template) or _is_within(stage, target):
            parser.error("--stage-review must be outside both the template and target trees")
    try:
        report = build_update_plan(template, target)
    except ValueError as exc:
        parser.error(str(exc))
    report["copied_missing"] = apply_missing_files(template, target, report) if args.apply_missing else []
    report["staged_review"] = stage_review_files(template, stage, report, overwrite=args.overwrite_stage, target=target) if args.stage_review else []
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
