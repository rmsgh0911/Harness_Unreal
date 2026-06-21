"""Check template-release hygiene without modifying files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel


TEXT_SUFFIXES = {".md", ".json", ".py", ".ps1", ".cmd", ".toml", ".sh"}
DUPLICATED_WORK_PATHS = ("Harness/work/work/",)
# Matches string literals like "Harness/docs/ProjectName/" that indicate a
# project-specific path was hardcoded into a template tool file.
_PROJECT_DOC_PATH_PATTERN = re.compile(
    r"(?P<quote>[\"'])Harness[\\/]docs[\\/](?P<folder>[^/\\\"']+)[\\/][^\"']*(?P=quote)"
)
GENERIC_TEMPLATE_DOC_FOLDERS = {"examples"}


def _has_utf8_bom(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    data = path.read_bytes()[:3]
    return data == b"\xef\xbb\xbf"


def build_report(root: Path, strict: bool = False) -> dict:
    harness = root / "Harness"
    errors: list[dict] = []
    warnings: list[dict] = []

    generated = [
        *sorted(harness.rglob("__pycache__")),
        *sorted(harness.rglob("*.pyc")),
    ]
    for path in generated:
        errors.append({"path": rel(path, root), "message": "generated_python_cache"})

    for old_path in [harness / "state.md", harness / "next.md", harness / "cycles"]:
        if old_path.exists():
            errors.append({"path": rel(old_path, root), "message": "old_work_layout_path"})
    for old_path in [harness / name for name in ["Codex", "Claude", "Common", "doc"]]:
        if old_path.exists():
            errors.append({"path": rel(old_path, root), "message": "legacy_split_or_old_layout_path"})

    for path in sorted(root.rglob("*")):
        if any(part in {".git", ".claude", "Binaries", "Intermediate", "Saved", "DerivedDataCache"} for part in path.parts):
            continue
        if path.is_symlink():
            errors.append({"path": rel(path, root), "message": "template_symlink_not_allowed"})
            continue
        if _has_utf8_bom(path):
            warnings.append({"path": rel(path, root), "message": "utf8_bom"})
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            if path.name == "harness_release_check.py":
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            if any(duplicated in text for duplicated in DUPLICATED_WORK_PATHS):
                errors.append({"path": rel(path, root), "message": "duplicated_work_path"})

    for script_path in sorted((harness / "scripts").rglob("*")):
        if not script_path.is_file() or script_path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if script_path.name == "harness_release_check.py":
            continue
        try:
            script_text = script_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        leaked_folders = sorted({
            match.group("folder")
            for match in _PROJECT_DOC_PATH_PATTERN.finditer(script_text)
            if match.group("folder").casefold() not in GENERIC_TEMPLATE_DOC_FOLDERS
            and not any(marker in match.group("folder") for marker in "*?<[{")
        })
        if leaked_folders:
            errors.append({
                "path": rel(script_path, root),
                "message": "hardcoded_project_doc_path_in_script:" + ",".join(leaked_folders),
            })

    cycle_root = harness / "work" / "cycles"
    cycle_files = sorted(
        path for path in cycle_root.rglob("*")
        if path.is_file() and rel(path, root) != "Harness/work/cycles/.gitkeep"
    )
    if cycle_files:
        warnings.append({"path": "Harness/work/cycles/", "message": f"cycle_logs_present:{len(cycle_files)}"})
    task_root = harness / "work" / "tasks"
    allowed_task_files = {"Harness/work/tasks/README.md", "Harness/work/tasks/task.example.md"}
    task_files = sorted(path for path in task_root.rglob("*") if path.is_file() and rel(path, root) not in allowed_task_files)
    if task_files:
        warnings.append({"path": "Harness/work/tasks/", "message": f"real_task_records_present:{len(task_files)}"})
    archive_root = harness / "work" / "archive"
    archive_files = sorted(
        path for path in archive_root.rglob("*")
        if path.is_file() and rel(path, root) != "Harness/work/archive/README.md"
    )
    if archive_files:
        warnings.append({"path": "Harness/work/archive/", "message": f"archived_work_records_present:{len(archive_files)}"})

    project = load_json(harness / "config" / "project.json", {}) or {}
    if isinstance(project, dict) and project.get("template_mode"):
        progress_text = read_text(harness / "Progress.md")
        required_sections = {"현재 상태", "최근 완료", "확인 필요", "다음 작업"}
        section_bullets: dict[str, list[str]] = {section: [] for section in required_sections}
        current_section = ""
        for line in progress_text.splitlines():
            if line.startswith("## "):
                current_section = line[3:].strip()
            elif current_section in required_sections and line.strip().startswith("- "):
                section_bullets[current_section].append(line.strip()[2:].strip())
        neutral = all(
            len(section_bullets[section]) == 1 and section_bullets[section][0].startswith("작성 필요:")
            for section in required_sections
        )
        if not neutral:
            errors.append({"path": "Harness/Progress.md", "message": "template_progress_contains_project_activity"})

    return {
        "root": str(root),
        "ok": not errors and not (strict and warnings),
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "guidance": "Run before packaging or copying the template into another project.",
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Release Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Strict: {report['strict']}",
        f"- Errors: {len(report['errors'])}",
        f"- Warnings: {len(report['warnings'])}",
    ]
    if report["errors"]:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["errors"])
    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["warnings"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness template release hygiene.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as release blockers.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, strict=args.strict)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
