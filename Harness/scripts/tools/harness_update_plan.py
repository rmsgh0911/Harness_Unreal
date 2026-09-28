"""Plan a reviewed Harness template update without overwriting project-owned data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, load_json, rel
from harness_migration_audit import audit
from harness_release_pack import collect_files
from harness_template_manifest import MANIFEST_RELATIVE, VALID_OWNERS, classify_owner, file_sha256


PROJECT_OWNED_FILES = {
    "Harness/config/project.json",
    "Harness/config/docs.json",
    "Harness/config/generated_artifacts.json",
    "Harness/config/local_rules.md",
    "Harness/config/record_policy.json",
    "Harness/config/sensitive_allowlist.json",
    "Harness/Progress.md",
}
PROJECT_OWNED_PREFIXES = (
    "Harness/docs/",
    "Harness/index/",
    "Harness/work/",
    # Reviewed memory shards are project data; the template ships only the
    # empty directory marker and the example shard outside this prefix.
    "Harness/data/memory/",
    "Harness/scripts/project/",
)
TEMPLATE_DOC_PREFIX = "Harness/docs/template/"
# Template-owned scaffolding that lives inside project-owned directories.
# Without this list these guidance files would stay "preserve" forever and
# never receive template updates (for example an archive README that predates
# newer archive modes).
TEMPLATE_SCAFFOLDING_FILES = {
    "Harness/docs/README.md",
    "Harness/docs/examples/cycle_log.example.md",
    "Harness/index/README.md",
    "Harness/work/README.md",
    "Harness/work/archive/README.md",
    "Harness/work/tasks/README.md",
    "Harness/work/tasks/task.example.md",
}
MERGE_REVIEW_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "HARNESS.md",
    ".gitattributes",
    ".gitignore",
    "Harness/README.md",
    "Harness/docs/template/setup.md",
    "Harness/docs/template/changelog.md",
    "Harness/config/agents.json",
    "Harness/config/cycle_policy.json",
    *TEMPLATE_SCAFFOLDING_FILES,
}
RECEIPT_RELATIVE = "Harness/config/template_receipt.json"
TEXT_SUFFIXES = {".cmd", ".json", ".jsonl", ".md", ".ps1", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml"}


def _is_project_owned(relative: str) -> bool:
    if relative == TEMPLATE_DOC_PREFIX.rstrip("/") or relative.startswith(TEMPLATE_DOC_PREFIX):
        return False
    if relative in TEMPLATE_SCAFFOLDING_FILES:
        return False
    return relative in PROJECT_OWNED_FILES or any(relative == prefix.rstrip("/") or relative.startswith(prefix) for prefix in PROJECT_OWNED_PREFIXES)


def _same_bytes(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.read_bytes() == right.read_bytes()


def _hash_if_file(path: Path) -> str | None:
    return file_sha256(path) if path.is_file() else None


def _newline_normalized_hash(path: Path) -> str | None:
    if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _difference_kind(source: Path, destination: Path, new_hash: str | None, local_hash: str | None) -> str:
    if local_hash is None:
        return "missing_local"
    if new_hash == local_hash:
        return "none"
    source_text_hash = _newline_normalized_hash(source)
    destination_text_hash = _newline_normalized_hash(destination)
    if source_text_hash is not None and source_text_hash == destination_text_hash:
        return "newline_only"
    return "content"


def _template_contract(template: Path) -> dict | None:
    try:
        manifest = load_json(template / MANIFEST_RELATIVE, None)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        return None
    rules = manifest.get("ownership_rules")
    if not isinstance(rules, list) or not rules:
        return None
    return manifest


def _owner_for(relative: str, contract: dict | None) -> str:
    if contract is not None:
        owner = classify_owner(relative, contract["ownership_rules"])
        if owner in VALID_OWNERS:
            return owner
    if _is_project_owned(relative):
        return "project_owned"
    if relative in MERGE_REVIEW_PATHS:
        return "managed_merge"
    return "template_owned"


def _load_receipt(target: Path) -> tuple[dict | None, dict]:
    path = target / RECEIPT_RELATIVE
    if not path.exists():
        return None, {"status": "missing", "path": RECEIPT_RELATIVE, "baseline": "unknown"}
    try:
        receipt = load_json(path, None)
    except (OSError, ValueError, TypeError):
        return None, {"status": "invalid", "path": RECEIPT_RELATIVE, "baseline": "unknown"}
    if not isinstance(receipt, dict) or receipt.get("schema_version") != 1 or not isinstance(receipt.get("files"), dict):
        return None, {"status": "invalid", "path": RECEIPT_RELATIVE, "baseline": "unknown"}
    for relative, entry in receipt["files"].items():
        if (
            not isinstance(relative, str)
            or not isinstance(entry, dict)
            or entry.get("owner") not in {"template_owned", "managed_merge"}
            or not isinstance(entry.get("baseline_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["baseline_sha256"])
        ):
            return None, {"status": "invalid", "path": RECEIPT_RELATIVE, "baseline": "unknown"}
    return receipt, {
        "status": "valid",
        "path": RECEIPT_RELATIVE,
        "baseline": "known",
        "template_version": receipt.get("template_version"),
        "file_count": len(receipt["files"]),
    }


def _known_baseline_action(
    *,
    destination_exists: bool,
    base_hash: str | None,
    local_hash: str | None,
    new_hash: str,
) -> tuple[str, str]:
    if base_hash is None:
        if not destination_exists:
            return "safe_add", "new_upstream_file"
        if local_hash == new_hash:
            return "unchanged", "already_matches_upstream"
        return "merge_review", "new_upstream_path_collides_with_local_file"
    if not destination_exists:
        if new_hash == base_hash:
            return "keep_local", "locally_deleted_upstream_unchanged"
        return "merge_review", "local_deletion_and_upstream_change"
    if local_hash == new_hash:
        return "unchanged", "local_matches_new_upstream"
    local_changed = local_hash != base_hash
    upstream_changed = new_hash != base_hash
    if not local_changed and upstream_changed:
        return "safe_replace", "upstream_only_change"
    if local_changed and not upstream_changed:
        return "keep_local", "project_only_change"
    return "merge_review", "both_changed"


def _manifest_tool_names(root: Path) -> set[str]:
    manifest = load_json(root / "Harness" / "scripts" / "tools" / "tool_manifest.json", {}) or {}
    tools = manifest.get("tools", []) if isinstance(manifest, dict) else []
    return {str(tool.get("name", "")) for tool in tools if isinstance(tool, dict) and tool.get("name")}


def _custom_manifest_entries(template: Path, target: Path) -> list[str]:
    """Tool registrations that exist only in the target manifest.

    Applying the template manifest wholesale would silently drop these; the
    review must merge them back (harness_doctor flags the loss afterwards).
    """
    return sorted(_manifest_tool_names(target) - _manifest_tool_names(template))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _roots_are_nested(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left != right and (_is_within(left, right) or _is_within(right, left))


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
    if target.exists() and _roots_are_nested(template, target):
        raise ValueError("template and target roots must be separate, non-nested directory trees")
    actions: list[dict] = []
    template_files = validate_template_root(template)
    contract = _template_contract(template)
    receipt, receipt_status = _load_receipt(target)
    template_relatives = {rel(path, template) for path in template_files}
    for source in template_files:
        relative = rel(source, template)
        destination = target / relative
        owner = _owner_for(relative, contract)
        new_hash = file_sha256(source)
        local_hash = _hash_if_file(destination)
        receipt_entry = receipt.get("files", {}).get(relative) if receipt is not None else None
        base_hash = receipt_entry.get("baseline_sha256") if isinstance(receipt_entry, dict) else None
        difference = _difference_kind(source, destination, new_hash, local_hash)
        if owner in {"project_owned", "generated_receipt"}:
            action = "preserve" if destination.exists() else "initialize_missing"
            reason = owner if destination.exists() else f"missing_{owner}_template"
        elif receipt is not None and contract is not None:
            action, reason = _known_baseline_action(
                destination_exists=destination.exists(),
                base_hash=base_hash,
                local_hash=local_hash,
                new_hash=new_hash,
            )
        elif owner == "managed_merge":
            action = "add" if not destination.exists() else ("unchanged" if _same_bytes(source, destination) else "merge_review")
            reason = "shared_policy_or_repository_rules"
        else:
            action = "add" if not destination.exists() else ("unchanged" if _same_bytes(source, destination) else "replace_review")
            reason = "standard_template_file"
        actions.append({
            "path": relative,
            "owner": owner,
            "action": action,
            "reason": reason,
            "baseline_status": "known" if base_hash is not None else "unknown",
            "base_hash": base_hash,
            "local_hash": local_hash,
            "new_hash": new_hash,
            "difference": difference,
        })

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

    action_by_path = {item["path"]: item["action"] for item in actions}
    added_paths = [item["path"] for item in actions if item["action"] in {"add", "safe_add", "initialize_missing"}]
    post_apply_notes: list[str] = []
    new_tool_scripts = [path for path in added_paths if path.startswith("Harness/scripts/tools/") and path.endswith(".py")]
    manifest_pending = action_by_path.get("Harness/scripts/tools/tool_manifest.json") in {"merge_review", "replace_review"}
    if new_tool_scripts and manifest_pending:
        post_apply_notes.append(
            "new tool scripts stay unregistered in the target tool_manifest.json until the manifest review is applied; "
            "harness_doctor warns about them in this transitional state"
        )
    custom_manifest_entries = _custom_manifest_entries(template, target)
    if custom_manifest_entries and manifest_pending:
        post_apply_notes.append(
            "the target tool_manifest.json registers custom tools that the template manifest does not know; "
            "re-merge these entries instead of replacing the manifest wholesale: " + ", ".join(custom_manifest_entries)
        )
    if any(path.startswith("Harness/data/") for path in added_paths):
        post_apply_notes.append(
            "the optional memory/data layer was added: merge .gitignore first so Harness/data SQLite caches are never committed, "
            "then validate with the target Harness launcher's memory --doctor command"
        )
    if "Harness/Progress_index.html" in added_paths or "Harness/Progress_view.cmd" in added_paths:
        post_apply_notes.append(
            "the Progress viewer was added: open it live with Harness/Progress_view.cmd or the launcher's progress --serve command "
            "(browsers block local fetch() over file://)"
        )
    if receipt_status["status"] == "missing":
        post_apply_notes.append(
            "template receipt is missing, so existing-file decisions use conservative two-way review; "
            "do not infer an installation baseline from matching timestamps or the current checkout"
        )
    elif receipt_status["status"] == "invalid":
        post_apply_notes.append(
            "template receipt is malformed and was ignored; repair or replace it only after a verified update"
        )

    recommended_sequence = [
        "commit or back up the target project before applying additions",
        "apply only missing files, then review staged merge/replace candidates",
        "preserve project-owned config, docs, index, work records, Progress, and custom tools",
    ]
    if any(path.startswith("Harness/data/") for path in added_paths):
        recommended_sequence.append("merge .gitignore data exclusions before the first commit that touches Harness/data/")
    recommended_sequence.extend(
        [
            "run the launcher's knowledge command to reuse existing Harness material",
            "run the launcher's verify command and inspect git diff --stat before removing legacy paths",
        ]
    )

    return {
        "template": str(template),
        "target": str(target),
        "same_root": template == target,
        "layout": migration["layout"],
        "ownership_source": MANIFEST_RELATIVE if contract is not None else "legacy_path_rules",
        "receipt": receipt_status,
        "counts": counts,
        "actions": actions,
        "custom_tools": custom_tools,
        "custom_manifest_entries": custom_manifest_entries,
        "preserve": migration["preserve"],
        "cleanup_after_verification": migration["cleanup"],
        "post_apply_notes": post_apply_notes,
        "recommended_sequence": recommended_sequence,
    }


def apply_missing_files(template: Path, target: Path, plan: dict) -> list[str]:
    if template.resolve() == target.resolve() or _roots_are_nested(template, target):
        raise ValueError("template and target must be separate, non-nested directory trees when applying files")
    if not target.is_dir() or not (target / "Harness").is_dir():
        raise ValueError("target must be an existing project with a Harness directory; use the normal initialization flow for a new project")
    operations: list[tuple[str, Path, Path]] = []
    for item in plan["actions"]:
        if item["action"] not in {"add", "safe_add", "initialize_missing"}:
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
    candidates = [item for item in plan["actions"] if item["action"] in {"merge_review", "replace_review", "safe_replace"}]
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


def build_receipt(template: Path) -> dict:
    contract = _template_contract(template)
    if contract is None:
        raise ValueError("template receipt requires a valid schema-v2 template manifest")
    files: dict[str, dict] = {}
    for source in validate_template_root(template):
        relative = rel(source, template)
        owner = _owner_for(relative, contract)
        if owner not in {"template_owned", "managed_merge"} or relative == MANIFEST_RELATIVE:
            continue
        files[relative] = {"owner": owner, "baseline_sha256": file_sha256(source)}
    return {
        "schema_version": 1,
        "template_version": contract.get("template_version"),
        "upstream": contract.get("source", {}),
        "manifest_sha256": file_sha256(template / MANIFEST_RELATIVE),
        "files": dict(sorted(files.items())),
    }


def _verify_target(target: Path) -> bool:
    verifier = target / "Harness/scripts/tools/harness_verify_all.py"
    if not verifier.is_file():
        return False
    completed = subprocess.run(
        [sys.executable, "-B", str(verifier), "--root", str(target)],
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0


def accept_receipt(
    template: Path,
    target: Path,
    plan: dict,
    *,
    verifier: Callable[[Path], bool] | None = None,
    resolutions: dict | None = None,
) -> str:
    if template.resolve() == target.resolve() or _roots_are_nested(template, target):
        raise ValueError("template and target must be separate, non-nested directory trees when accepting an install receipt")
    _planned_paths(target, RECEIPT_RELATIVE)
    # Rebuild at acceptance time: callers must not acknowledge a stale plan.
    plan = build_update_plan(template, target)
    resolutions = {} if resolutions is None else resolutions
    if not isinstance(resolutions, dict):
        raise ValueError("resolutions must be an object keyed by reviewed path")
    reviewed_actions = {item["path"]: item for item in plan["actions"]}
    for relative, resolution in resolutions.items():
        item = reviewed_actions.get(relative)
        if not isinstance(resolution, dict) or not item or item["owner"] not in {"managed_merge", "template_owned"}:
            raise ValueError(f"invalid review resolution: {relative}")
        if item["action"] not in {"merge_review", "replace_review", "unchanged", "keep_local"}:
            raise ValueError(f"review resolution cannot accept an unapplied file: {relative}")
        if not isinstance(resolution.get("reason"), str) or not resolution["reason"].strip():
            raise ValueError(f"review resolution requires a reason: {relative}")
        if not item["local_hash"] or resolution.get("local_sha256") != item["local_hash"] or resolution.get("upstream_sha256") != item["new_hash"]:
            raise ValueError(f"review resolution hashes are stale: {relative}")
    unresolved = [
        item["path"]
        for item in plan["actions"]
        if item.get("owner") in {"template_owned", "managed_merge"}
        and item.get("action") not in {"unchanged", "keep_local"}
        and item["path"] not in resolutions
    ]
    if unresolved:
        raise ValueError("receipt cannot be accepted while template changes remain unapplied or unreviewed: " + ", ".join(unresolved[:8]))
    check = verifier or _verify_target
    if not check(target):
        raise RuntimeError("target verification failed; template receipt was not written")

    # Verification may invoke project code; refuse provenance for a changed tree.
    after = build_update_plan(template, target)
    fingerprint = lambda report: [(item["path"], item["local_hash"], item["new_hash"], item["owner"], item["action"]) for item in report["actions"]]
    if fingerprint(after) != fingerprint(plan):
        raise ValueError("template or target changed during verification; review a fresh plan")

    receipt = build_receipt(template)
    if resolutions:
        receipt["reviewed_resolutions"] = resolutions
    path, _ = _planned_paths(target, RECEIPT_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".template-receipt-", suffix=".json.tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return RECEIPT_RELATIVE


def format_text(report: dict) -> str:
    lines = [
        "Harness Update Plan",
        f"- Template: {report['template']}",
        f"- Target: {report['target']}",
        f"- Target layout: {report['layout']['kind']}",
        f"- Ownership: {report['ownership_source']}",
        f"- Receipt: {report['receipt']['status']} ({report['receipt']['baseline']} baseline)",
        f"- Custom tools preserved: {len(report['custom_tools'])}",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(report["counts"].items()))
    for title, actions in [
        ("Safe Replace (review/apply pending)", {"safe_replace"}),
        ("Merge Review", {"merge_review"}),
        ("Replace Review", {"replace_review"}),
        ("Kept Local", {"keep_local"}),
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
    if report.get("post_apply_notes"):
        lines.extend(["", "Post-Apply Notes:", *(f"- {item}" for item in report["post_apply_notes"])])
    newline_only = [item["path"] for item in report["actions"] if item.get("difference") == "newline_only"]
    if newline_only:
        lines.extend(["", "Newline-Only Differences:", *(f"- {item}" for item in newline_only[:30])])
    lines.extend(["", "Recommended Sequence:", *(f"- {item}" for item in report["recommended_sequence"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a new Harness template with an older target install.")
    parser.add_argument("--template", type=Path, default=None, help="New template root. Defaults to the current Harness template root.")
    parser.add_argument("--target", type=Path, required=True, help="Older project root to update.")
    parser.add_argument("--apply-missing", action="store_true", help="Copy only files that do not exist in the target. Never overwrites.")
    parser.add_argument("--stage-review", type=Path, default=None, help="Copy merge/replace candidates into this separate review directory.")
    parser.add_argument("--overwrite-stage", action="store_true", help="Allow --stage-review to replace files already present in the review directory.")
    parser.add_argument("--accept-receipt", action="store_true", help="Write installed provenance only when all template changes are resolved and target verification passes.")
    parser.add_argument("--resolutions", type=Path, default=None, help="JSON file mapping reviewed paths to local_sha256, upstream_sha256, and reason; requires --accept-receipt.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if args.overwrite_stage and not args.stage_review:
        parser.error("--overwrite-stage requires --stage-review")
    if args.accept_receipt and (args.apply_missing or args.stage_review):
        parser.error("--accept-receipt must be a separate post-verification invocation after applying or reviewing files")
    if args.resolutions and not args.accept_receipt:
        parser.error("--resolutions requires --accept-receipt")
    template = find_project_root(args.template).resolve()
    target = args.target.resolve()
    if args.stage_review:
        stage = args.stage_review.resolve()
        if _is_within(stage, template) or _is_within(stage, target):
            parser.error("--stage-review must be outside both the template and target trees")
    try:
        report = build_update_plan(template, target)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    try:
        report["copied_missing"] = apply_missing_files(template, target, report) if args.apply_missing else []
        report["staged_review"] = stage_review_files(template, stage, report, overwrite=args.overwrite_stage, target=target) if args.stage_review else []
        resolutions = load_json(args.resolutions, None) if args.resolutions else None
        if args.resolutions and not isinstance(resolutions, dict):
            raise ValueError("--resolutions must contain a JSON object keyed by reviewed path")
        report["accepted_receipt"] = accept_receipt(template, target, report, resolutions=resolutions) if args.accept_receipt else None
    except (OSError, RuntimeError, ValueError, shutil.Error) as exc:
        parser.error(str(exc))
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
