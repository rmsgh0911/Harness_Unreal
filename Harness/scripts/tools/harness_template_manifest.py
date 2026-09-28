"""Build and verify the deterministic Harness template inventory and ownership map."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, load_json, rel


MANIFEST_RELATIVE = "Harness/template/manifest.json"
ROOT_FILES = (
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "HARNESS.md",
    "README.md",
)
EXCLUDED_PARTS = {
    ".claude",
    ".git",
    ".runtime",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "Binaries",
    "DerivedDataCache",
    "Intermediate",
    "Saved",
    "__pycache__",
    "dist",
}
EXCLUDED_NAMES = {"handoff.md"}
EXCLUDED_SUFFIXES = {".db", ".pyc", ".sqlite"}
WORKSPACE_ONLY_ROOTS = (("Harness", "temp"),)
HASHED_OWNERS = {"template_owned", "managed_merge"}
VALID_OWNERS = {*HASHED_OWNERS, "project_owned", "generated_receipt"}
DEFAULT_OWNERSHIP_RULES = [
    {
        "owner": "generated_receipt",
        "patterns": [
            "Harness/config/template_receipt.json",
            "Harness/template.lock.json",
        ],
    },
    {
        "owner": "managed_merge",
        "patterns": [
            ".gitattributes",
            ".gitignore",
            "AGENTS.md",
            "CLAUDE.md",
            "HARNESS.md",
            "README.md",
            "Harness/README.md",
            "Harness/docs/AgentFieldGuide.md",
            "Harness/docs/README.md",
            "Harness/index/README.md",
            "Harness/scripts/build/**",
            "Harness/scripts/tools/tool_manifest.json",
            "Harness/scripts/unreal/**",
            "Harness/work/README.md",
            "Harness/work/archive/README.md",
            "Harness/work/tasks/README.md",
            "Harness/work/tasks/task.example.md",
        ],
    },
    {
        "owner": "project_owned",
        "patterns": [
            "Harness/Progress.md",
            "Harness/config/docs.json",
            "Harness/config/generated_artifacts.json",
            "Harness/config/local_rules.md",
            "Harness/config/project.json",
            "Harness/config/record_policy.json",
            "Harness/config/sensitive_allowlist.json",
            "Harness/data/memory/**",
            "Harness/docs/project/**",
            "Harness/index/**",
            "Harness/scripts/project/**",
            "Harness/work/**",
        ],
    },
    {"owner": "template_owned", "patterns": ["**"]},
]


def should_include(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    relative_text = relative.as_posix()
    parts = set(relative.parts)
    if path.is_symlink() or parts & EXCLUDED_PARTS:
        return False
    if any(relative.parts[: len(prefix)] == prefix for prefix in WORKSPACE_ONLY_ROOTS):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES or path.name.endswith((".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm")):
        return False
    if len(relative.parts) >= 3 and relative.parts[:3] == ("Harness", "data", "memory"):
        return relative_text == "Harness/data/memory/.gitkeep"
    if len(relative.parts) >= 3 and relative.parts[:3] == ("Harness", "work", "cycles"):
        return relative_text == "Harness/work/cycles/.gitkeep"
    if len(relative.parts) >= 3 and relative.parts[:3] == ("Harness", "work", "tasks"):
        return relative_text in {"Harness/work/tasks/README.md", "Harness/work/tasks/task.example.md"}
    if len(relative.parts) >= 3 and relative.parts[:3] == ("Harness", "work", "archive"):
        return relative_text == "Harness/work/archive/README.md"
    return True


def discover_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in ROOT_FILES:
        path = root / relative
        if path.is_file() and should_include(path, root):
            files.append(path)
    harness = root / "Harness"
    if harness.exists():
        for current, directory_names, file_names in os.walk(harness, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_directories: list[str] = []
            for name in directory_names:
                candidate = current_path / name
                try:
                    relative_parts = candidate.relative_to(root).parts
                except ValueError:
                    continue
                if candidate.is_symlink() or name in EXCLUDED_PARTS:
                    continue
                if any(relative_parts[: len(prefix)] == prefix for prefix in WORKSPACE_ONLY_ROOTS):
                    continue
                kept_directories.append(name)
            directory_names[:] = kept_directories
            files.extend(
                candidate
                for name in file_names
                if (candidate := current_path / name).is_file() and should_include(candidate, root)
            )
    return sorted(set(files), key=lambda path: rel(path, root).casefold())


def _safe_manifest_relative(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0] not in {*ROOT_FILES, "Harness"}:
        return None
    return path.as_posix()


def classify_owner(relative: str, rules: list[dict]) -> str:
    for rule in rules:
        owner = rule.get("owner")
        patterns = rule.get("patterns")
        if owner not in VALID_OWNERS or not isinstance(patterns, list):
            continue
        if any(isinstance(pattern, str) and fnmatch.fnmatchcase(relative, pattern) for pattern in patterns):
            return owner
    return "template_owned"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, current: dict | None = None) -> dict:
    current = current if isinstance(current, dict) else {}
    rules = current.get("ownership_rules")
    if current.get("ownership_schema_version") != 1 or not isinstance(rules, list) or not rules:
        rules = DEFAULT_OWNERSHIP_RULES
    release_files = sorted({rel(path, root) for path in discover_release_files(root)} | {MANIFEST_RELATIVE})
    hashes = {
        relative: file_sha256(root / relative)
        for relative in release_files
        if relative != MANIFEST_RELATIVE
        and (root / relative).is_file()
        and classify_owner(relative, rules) in HASHED_OWNERS
    }
    source = current.get("source")
    if not isinstance(source, dict):
        source = {"repository": "https://github.com/rmsgh0911/Harness_Unreal", "commit": None}
    return {
        "schema_version": 2,
        "ownership_schema_version": 1,
        "template_version": current.get("template_version", "0.2.0-dev"),
        "source": source,
        "ownership_rules": rules,
        "release_files": release_files,
        "template_file_hashes": dict(sorted(hashes.items())),
    }


def release_files_from_manifest(root: Path) -> list[Path] | None:
    path = root / MANIFEST_RELATIVE
    try:
        manifest = load_json(path, None)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("release_files"), list):
        return None
    files: list[Path] = []
    for value in manifest["release_files"]:
        relative = _safe_manifest_relative(value)
        if relative is None:
            continue
        candidate = root / relative
        if candidate.is_file() and should_include(candidate, root):
            files.append(candidate)
    return sorted(set(files), key=lambda candidate: rel(candidate, root).casefold())


def build_report(root: Path) -> dict:
    path = root / MANIFEST_RELATIVE
    issues: list[dict] = []
    try:
        current = load_json(path, None)
    except (OSError, ValueError, TypeError):
        current = None
        issues.append({"path": MANIFEST_RELATIVE, "message": "manifest_unreadable"})
    if not isinstance(current, dict):
        issues.append({"path": MANIFEST_RELATIVE, "message": "manifest_missing_or_invalid"})
        return {"root": str(root), "ok": False, "issues": issues, "file_count": 0, "hashed_file_count": 0}
    if current.get("schema_version") != 2:
        issues.append({"path": MANIFEST_RELATIVE, "message": "schema_version_must_be_2"})
    if current.get("ownership_schema_version") != 1:
        issues.append({"path": MANIFEST_RELATIVE, "message": "ownership_schema_version_must_be_1"})
    rules = current.get("ownership_rules")
    if not isinstance(rules, list) or not rules:
        issues.append({"path": MANIFEST_RELATIVE, "message": "ownership_rules_missing"})
    else:
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict) or rule.get("owner") not in VALID_OWNERS or not isinstance(rule.get("patterns"), list):
                issues.append({"path": MANIFEST_RELATIVE, "message": f"ownership_rule_invalid:{index}"})
    for value in current.get("release_files", []) if isinstance(current.get("release_files"), list) else []:
        if _safe_manifest_relative(value) is None:
            issues.append({"path": MANIFEST_RELATIVE, "message": "release_path_invalid"})
    expected = build_manifest(root, current)
    current_files = current.get("release_files")
    if current_files != expected["release_files"]:
        issues.append({"path": MANIFEST_RELATIVE, "message": "release_inventory_stale"})
    current_hashes = current.get("template_file_hashes")
    if current_hashes != expected["template_file_hashes"]:
        issues.append({"path": MANIFEST_RELATIVE, "message": "template_hashes_stale"})
    return {
        "root": str(root),
        "ok": not issues,
        "issues": issues,
        "file_count": len(expected["release_files"]),
        "hashed_file_count": len(expected["template_file_hashes"]),
        "ownership_counts": {
            owner: sum(classify_owner(relative, expected["ownership_rules"]) == owner for relative in expected["release_files"])
            for owner in sorted(VALID_OWNERS)
        },
    }


def write_manifest(root: Path) -> dict:
    path = root / MANIFEST_RELATIVE
    try:
        current = load_json(path, {})
    except (OSError, ValueError, TypeError):
        current = {}
    manifest = build_manifest(root, current)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".manifest-", suffix=".json.tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return manifest


def format_text(report: dict) -> str:
    lines = [
        "Harness Template Manifest",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Release files: {report['file_count']}",
        f"- Hashed template/merge files: {report['hashed_file_count']}",
    ]
    if report["issues"]:
        lines.extend(["", "Issues:"])
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["issues"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the template ownership and release inventory manifest.")
    parser.add_argument("--root", type=Path, default=None, help="Template root. Defaults to nearest Harness root.")
    parser.add_argument("--write", action="store_true", help="Atomically refresh inventory and hashes.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    if args.write:
        write_manifest(root)
    report = build_report(root)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
