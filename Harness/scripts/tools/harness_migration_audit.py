"""Audit an older Harness project before applying this template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, load_json, read_text, rel


ACTIVE_DOCS = ["HARNESS.md", "AGENTS.md", "CLAUDE.md", "README.md", "Harness/README.md", "Harness/state.md", "Harness/next.md"]
OLD_PATH_PATTERNS = [
    "Harness/scripts/verify_project.py",
    "Harness/scripts/create_level.py",
    "Harness/scripts/build_verify.ps1",
    "Harness/scripts/build_verify.cmd",
]
NEW_PATH_REPLACEMENTS = {
    "Harness/scripts/verify_project.py": "Harness/scripts/unreal/verify_project.py",
    "Harness/scripts/create_level.py": "Harness/scripts/unreal/create_level.py",
    "Harness/scripts/build_verify.ps1": "Harness/scripts/build/build_verify.ps1",
    "Harness/scripts/build_verify.cmd": "Harness/scripts/build/build_verify.cmd",
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
    scripts = root / "Harness" / "scripts"
    known = {"verify_project.py", "create_level.py", "build_verify.ps1", "build_verify.cmd"}
    custom: list[str] = []
    if not scripts.exists():
        return custom
    for item in scripts.iterdir():
        if item.is_file() and item.name not in known:
            custom.append(rel(item, root))
    return sorted(custom)


def current_template_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_bytes_if_exists(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        return b""
    return path.read_bytes()


def modified_standard_scripts(root: Path, template_root: Path) -> list[dict]:
    pairs = [
        ("Harness/scripts/verify_project.py", "Harness/scripts/unreal/verify_project.py"),
        ("Harness/scripts/create_level.py", "Harness/scripts/unreal/create_level.py"),
        ("Harness/scripts/build_verify.ps1", "Harness/scripts/build/build_verify.ps1"),
        ("Harness/scripts/build_verify.cmd", "Harness/scripts/build/build_verify.cmd"),
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
    config_path = root / "Harness" / "config" / "project.json"
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
    template_root = current_template_root()
    harness = root / "Harness"
    scripts = harness / "scripts"
    cycles = harness / "cycles"
    doc = harness / "doc"
    reviews = harness / "reviews"

    cycle_files = [name for name in list_names(cycles, "*.md") if name != ".gitkeep"]
    findings: list[dict] = []
    preserve: list[str] = []
    update: list[str] = []
    cleanup: list[str] = []

    if not harness.exists():
        findings.append({"level": "error", "message": "Harness directory is missing"})
    if existing(harness / "state.md"):
        preserve.append("Harness/state.md")
    if existing(harness / "next.md"):
        preserve.append("Harness/next.md")
    if cycle_files:
        preserve.append("Harness/cycles/")
    if doc.exists():
        preserve.append("Harness/doc/")
    if existing(harness / "config" / "project.json"):
        preserve.append("Harness/config/project.json")

    if existing(root / "Harness_Unreal"):
        cleanup.append("Harness_Unreal/")
        findings.append({"level": "warning", "message": "template source folder Harness_Unreal is present"})
    if existing(harness / "backlog.md"):
        cleanup.append("Harness/backlog.md after moving unresolved items into Harness/next.md")
        findings.append({"level": "warning", "message": "legacy Harness/backlog.md is present"})
    if reviews.exists():
        cleanup.append("Harness/reviews/ if no explicit external review workflow is required")
        findings.append({"level": "info", "message": "legacy external review folder is present"})

    root_script_names = list_names(scripts)
    old_script_layout = any(name in root_script_names for name in ["verify_project.py", "create_level.py", "build_verify.ps1", "build_verify.cmd"])
    if old_script_layout:
        update.append("move standard scripts to Harness/scripts/unreal/ and Harness/scripts/build/")
        findings.append({"level": "warning", "message": "standard scripts are in legacy Harness/scripts root"})
    if not existing(scripts / "tools" / "tool_manifest.json"):
        update.append("add Harness/scripts/tools/ and tool_manifest.json")
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
        update.append("replace old Harness/scripts/*.py and build_verify.* references in active docs")
        findings.append({"level": "warning", "message": f"old script path references in active docs: {len(old_refs)}"})

    project = project_config_summary(root)
    if not project["exists"]:
        findings.append({"level": "error", "message": "Harness/config/project.json is missing"})
    elif not project["build_configured"]:
        findings.append({"level": "warning", "message": "project.json build config is incomplete"})

    return {
        "root": str(root),
        "ok": not any(item["level"] == "error" for item in findings),
        "summary": {
            "cycle_files": len(cycle_files),
            "doc_files": len([name for name in list_names(doc) if name != ".gitkeep"]),
            "custom_scripts": len(custom_scripts),
            "modified_standard_scripts": len(modified_standard),
            "old_path_refs": len(old_refs),
            "findings": len(findings),
        },
        "project": project,
        "layout": {
            "has_harness": harness.exists(),
            "has_root_harness_md": existing(root / "HARNESS.md"),
            "has_agents_md": existing(root / "AGENTS.md"),
            "has_claude_md": existing(root / "CLAUDE.md"),
            "has_reviews": reviews.exists(),
            "has_backlog": existing(harness / "backlog.md"),
            "has_harness_unreal_source_folder": existing(root / "Harness_Unreal"),
            "old_script_layout": old_script_layout,
            "has_tools_manifest": existing(scripts / "tools" / "tool_manifest.json"),
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
