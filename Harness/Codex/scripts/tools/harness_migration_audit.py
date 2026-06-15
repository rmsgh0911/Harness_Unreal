"""Audit an older Harness project before applying this template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, load_json, read_text, rel


ACTIVE_DOCS = [
    "HARNESS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "Harness/README.md",
    "Harness/Codex/work/state.md",
    "Harness/Codex/work/next.md",
]
OLD_PATH_PATTERNS = [
    "Harness/Codex/scripts/verify_project.py",
    "Harness/Codex/scripts/create_level.py",
    "Harness/Codex/scripts/build_verify.ps1",
    "Harness/Codex/scripts/build_verify.cmd",
]
NEW_PATH_REPLACEMENTS = {
    "Harness/Codex/scripts/verify_project.py": "Harness/Codex/scripts/unreal/verify_project.py",
    "Harness/Codex/scripts/create_level.py": "Harness/Codex/scripts/unreal/create_level.py",
    "Harness/Codex/scripts/build_verify.ps1": "Harness/Codex/scripts/build/build_verify.ps1",
    "Harness/Codex/scripts/build_verify.cmd": "Harness/Codex/scripts/build/build_verify.cmd",
}


def existing(path: Path) -> bool:
    return path.exists()


def list_names(path: Path, pattern: str = "*") -> list[str]:
    if not path.exists():
        return []
    return sorted(item.name for item in path.glob(pattern))


def find_old_path_refs(root: Path) -> list[dict]:
    refs: list[dict] = []
    for relative in ACTIVE_DOCS:
        path = root / relative
        if not path.exists():
            continue
        text = read_text(path)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in OLD_PATH_PATTERNS:
                if pattern in line:
                    refs.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "old": pattern,
                            "new": NEW_PATH_REPLACEMENTS[pattern],
                        }
                    )
    return refs


def find_custom_root_scripts(root: Path) -> list[str]:
    worker_scripts = root / "Harness" / "Codex" / "scripts"
    scripts = worker_scripts if worker_scripts.exists() else root / "Harness" / "scripts"
    known = {"verify_project.py", "create_level.py", "build_verify.ps1", "build_verify.cmd"}
    custom: list[str] = []
    if not scripts.exists():
        return custom
    for item in scripts.iterdir():
        if item.is_file() and item.name not in known:
            custom.append(rel(item, root))
    return sorted(custom)


def this_installation_root() -> Path:
    """Return the root of the Harness installation that contains this script.

    Used to compare the target project's legacy-path standard scripts against
    the current installation's new-path scripts.  Run this tool from the
    up-to-date installation when auditing an older project:

        python /path/to/new/project/Harness/Codex/scripts/tools/harness_migration_audit.py \\
            --target /path/to/old/project
    """
    return Path(__file__).resolve().parents[4]


def read_bytes_if_exists(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        return b""
    return path.read_bytes()


def modified_standard_scripts(root: Path, template_root: Path) -> list[dict]:
    pairs = [
        ("Harness/Codex/scripts/verify_project.py", "Harness/Codex/scripts/unreal/verify_project.py"),
        ("Harness/Codex/scripts/create_level.py", "Harness/Codex/scripts/unreal/create_level.py"),
        ("Harness/Codex/scripts/build_verify.ps1", "Harness/Codex/scripts/build/build_verify.ps1"),
        ("Harness/Codex/scripts/build_verify.cmd", "Harness/Codex/scripts/build/build_verify.cmd"),
    ]
    modified: list[dict] = []
    for old_relative, new_relative in pairs:
        old_path = root / old_relative
        new_path = template_root / new_relative
        old_bytes = read_bytes_if_exists(old_path)
        new_bytes = read_bytes_if_exists(new_path)
        if old_bytes and new_bytes and old_bytes != new_bytes:
            modified.append(
                {
                    "old_path": old_relative,
                    "template_path": new_relative,
                    "old_size": len(old_bytes),
                    "template_size": len(new_bytes),
                }
            )
    return modified


def project_config_summary(root: Path) -> dict:
    worker_config = root / "Harness" / "Codex" / "config" / "project.json"
    config_path = worker_config if worker_config.exists() else root / "Harness" / "config" / "project.json"
    data = load_json(config_path, {}) or {}
    build = data.get("build", {}) if isinstance(data, dict) else {}
    return {
        "exists": config_path.exists(),
        "project_name": data.get("project_name", "") if isinstance(data, dict) else "",
        "uproject_file": data.get("uproject_file", "") if isinstance(data, dict) else "",
        "engine_version": data.get("engine_version", "") if isinstance(data, dict) else "",
        "required_classes": len(data.get("required_classes", [])) if isinstance(data, dict) else 0,
        "required_assets": len(data.get("required_assets", [])) if isinstance(data, dict) else 0,
        "required_source_marker_files": len(data.get("required_source_markers", {})) if isinstance(data, dict) else 0,
        "required_config_marker_files": len(data.get("required_config_markers", {})) if isinstance(data, dict) else 0,
        "build_configured": bool(build.get("engine_root") and build.get("editor_target_name")),
    }


def audit(root: Path) -> dict:
    template_root = this_installation_root()
    harness = root / "Harness"
    worker_harness = harness / "Codex"
    scripts = worker_harness / "scripts" if worker_harness.exists() else harness / "scripts"
    work = worker_harness / "work" if worker_harness.exists() else harness / "work"
    cycles = work / "cycles"
    legacy_cycles = harness / "cycles"
    index = worker_harness / "index" if worker_harness.exists() else harness / "index"
    common_docs = harness / "Common" / "docs"
    harness_docs = common_docs if common_docs.exists() else harness / "docs"
    legacy_doc = harness / "doc"
    project_docs = root / "ProjectDocs"
    reviews = harness / "reviews"

    cycle_files = [name for name in list_names(cycles, "*.md") if name != ".gitkeep"]
    legacy_cycle_files = [name for name in list_names(legacy_cycles, "*.md") if name != ".gitkeep"]
    findings: list[dict] = []
    preserve: list[str] = []
    update: list[str] = []
    cleanup: list[str] = []
    has_worker_layout = worker_harness.exists()
    has_legacy_layout = any(
        (harness / name).exists() for name in ["config", "scripts", "index", "work", "docs", "doc"]
    )

    if not harness.exists():
        findings.append({"level": "error", "message": "Harness directory is missing"})
    elif has_legacy_layout and not has_worker_layout:
        findings.append({"level": "warning", "message": "legacy single-worker Harness layout detected"})
        update.append("migrate legacy single-worker Harness data into both Harness/Codex/ and Harness/Claude/ before removing legacy paths")
    if existing(work / "state.md"):
        preserve.append("Harness/Codex/work/state.md" if has_worker_layout else "Harness/work/state.md")
        if not has_worker_layout:
            update.append("copy or merge Harness/work/state.md into both worker state files as an initial snapshot")
    elif existing(harness / "state.md"):
        update.append("move Harness/state.md to Harness/Codex/work/state.md")
        preserve.append("Harness/state.md")
    if existing(work / "next.md"):
        preserve.append("Harness/Codex/work/next.md" if has_worker_layout else "Harness/work/next.md")
        if not has_worker_layout:
            update.append("copy or merge Harness/work/next.md into both worker next files as an initial snapshot")
    elif existing(harness / "next.md"):
        update.append("move Harness/next.md to Harness/Codex/work/next.md")
        preserve.append("Harness/next.md")
    if cycle_files:
        preserve.append("Harness/Codex/work/cycles/" if has_worker_layout else "Harness/work/cycles/")
        if not has_worker_layout:
            update.append("preserve legacy Harness/work/cycles/ and seed both worker cycle histories only when useful")
    elif legacy_cycle_files or existing(legacy_cycles):
        update.append("move Harness/cycles/ to Harness/Codex/work/cycles/")
        preserve.append("Harness/cycles/")
    if index.exists():
        preserve.append("Harness/Codex/index/" if has_worker_layout else "Harness/index/")
        if not has_worker_layout:
            update.append("copy or merge legacy Harness/index/ into both worker index areas as an initial snapshot")
    if harness_docs.exists():
        preserve.append("Harness/Common/docs/" if common_docs.exists() else "Harness/docs/")
        if not common_docs.exists():
            update.append("move or merge confirmed legacy Harness/docs/ documents into Harness/Common/docs/")
    if project_docs.exists():
        preserve.append("ProjectDocs/ as optional external docs")
    if legacy_doc.exists():
        preserve.append("Harness/doc/ until migrated to Harness/Common/docs/")
        update.append("migrate legacy Harness/doc project documents to Harness/Common/docs/ or register the existing folder in Harness/Codex/config/docs.json")
        findings.append({"level": "warning", "message": "legacy Harness/doc exists; migrate project documents to Harness/Common/docs"})
    config = worker_harness / "config" if worker_harness.exists() else harness / "config"
    if existing(config / "project.json"):
        preserve.append("Harness/Codex/config/project.json" if has_worker_layout else "Harness/config/project.json")
        if not has_worker_layout:
            update.append("copy or merge Harness/config/project.json into both worker project.json files")
    if existing(config / "docs.json"):
        preserve.append("Harness/Codex/config/docs.json" if has_worker_layout else "Harness/config/docs.json")
        if not has_worker_layout:
            update.append("copy or merge Harness/config/docs.json into both worker docs.json files and point them at Harness/Common/docs")
    else:
        update.append("add Harness/Codex/config/docs.json")

    if existing(root / "Harness_Unreal"):
        cleanup.append("Harness_Unreal/")
        findings.append({"level": "warning", "message": "template source folder Harness_Unreal is present"})
    if existing(harness / "backlog.md"):
        cleanup.append("Harness/backlog.md after moving unresolved items into Harness/Codex/work/next.md")
        findings.append({"level": "warning", "message": "legacy Harness/backlog.md is present"})
    if reviews.exists():
        cleanup.append("Harness/reviews/ if no explicit external review workflow is required")
        findings.append({"level": "info", "message": "legacy external review folder is present"})

    root_script_names = list_names(scripts)
    old_script_layout = any(name in root_script_names for name in ["verify_project.py", "create_level.py", "build_verify.ps1", "build_verify.cmd"])
    if old_script_layout:
        update.append("move standard scripts to Harness/Codex/scripts/unreal/ and Harness/Codex/scripts/build/")
        findings.append({"level": "warning", "message": "standard scripts are in legacy Harness/Codex/scripts root"})
    if not existing(scripts / "tools" / "tool_manifest.json"):
        update.append("add Harness/Codex/scripts/tools/ and tool_manifest.json")
        findings.append({"level": "warning", "message": "agent tools directory or manifest is missing"})

    custom_scripts = find_custom_root_scripts(root)
    modified_standard = modified_standard_scripts(root, template_root)
    if custom_scripts:
        preserve.extend(custom_scripts)
        findings.append({"level": "info", "message": f"custom root scripts detected: {len(custom_scripts)}"})
    if modified_standard:
        preserve.extend(item["old_path"] for item in modified_standard)
        update.append("merge project-modified standard scripts instead of blindly replacing them")
        findings.append({"level": "warning", "message": f"project-modified standard scripts detected: {len(modified_standard)}"})

    old_refs = find_old_path_refs(root)
    if old_refs:
        update.append("replace old Harness/Codex/scripts/*.py and build_verify.* references in active docs")
        findings.append({"level": "warning", "message": f"old script path references in active docs: {len(old_refs)}"})

    project = project_config_summary(root)
    if not project["exists"]:
        findings.append({"level": "error", "message": "Harness/Codex/config/project.json is missing"})
    elif not project["build_configured"]:
        findings.append({"level": "warning", "message": "project.json build config is incomplete"})

    return {
        "root": str(root),
        "ok": not any(item["level"] == "error" for item in findings),
        "summary": {
            "cycle_files": len(cycle_files),
            "legacy_cycle_files": len(legacy_cycle_files),
            "harness_docs_files": len([path for path in harness_docs.glob("**/*") if path.is_file() and path.name != ".gitkeep"]) if harness_docs.exists() else 0,
            "project_doc_files": len([path for path in project_docs.glob("**/*") if path.is_file()]) if project_docs.exists() else 0,
            "legacy_harness_doc_files": len([path for path in legacy_doc.glob("**/*") if path.is_file() and path.name != ".gitkeep"]) if legacy_doc.exists() else 0,
            "index_files": len([path for path in index.glob("**/*") if path.is_file() and path.name != ".gitkeep"]) if index.exists() else 0,
            "custom_scripts": len(custom_scripts),
            "modified_standard_scripts": len(modified_standard),
            "old_path_refs": len(old_refs),
            "findings": len(findings),
        },
        "project": project,
        "layout": {
            "kind": "worker_split" if has_worker_layout else ("legacy_single_worker" if has_legacy_layout else "missing_or_unknown"),
            "has_harness": harness.exists(),
            "has_root_harness_md": existing(root / "HARNESS.md"),
            "has_agents_md": existing(root / "AGENTS.md"),
            "has_claude_md": existing(root / "CLAUDE.md"),
            "has_reviews": reviews.exists(),
            "has_backlog": existing(harness / "backlog.md"),
            "has_harness_unreal_source_folder": existing(root / "Harness_Unreal"),
            "old_script_layout": old_script_layout,
            "has_tools_manifest": existing(scripts / "tools" / "tool_manifest.json"),
            "has_project_docs": project_docs.exists(),
            "has_harness_docs": harness_docs.exists(),
            "has_harness_index": index.exists(),
            "has_legacy_harness_doc": legacy_doc.exists(),
        },
        "old_path_refs": old_refs,
        "modified_standard_scripts": modified_standard,
        "preserve": sorted(set(preserve)),
        "update": sorted(set(update)),
        "cleanup": sorted(set(cleanup)),
        "findings": findings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Migration Audit",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Cycle files: {report['summary']['cycle_files']}",
        f"- Legacy cycle files: {report['summary']['legacy_cycle_files']}",
        f"- Custom scripts: {report['summary']['custom_scripts']}",
        f"- Modified standard scripts: {report['summary']['modified_standard_scripts']}",
        f"- Old path refs: {report['summary']['old_path_refs']}",
        f"- Project: {report['project']['project_name'] or 'not configured'}",
    ]
    for section in ["preserve", "update", "cleanup"]:
        lines.extend(["", section.capitalize() + ":"])
        items = report[section]
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    if report["findings"]:
        lines.extend(["", "Findings:"])
        lines.extend(f"- [{item['level']}] {item['message']}" for item in report["findings"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an older Harness project before template migration.")
    parser.add_argument("--target", type=Path, default=Path.cwd(), help="Target project root to audit.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = args.target.resolve()
    report = audit(root)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
