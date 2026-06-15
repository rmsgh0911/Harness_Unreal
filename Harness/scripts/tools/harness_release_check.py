"""Check template-release hygiene without modifying files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, rel


TEXT_SUFFIXES = {".md", ".json", ".py", ".ps1", ".cmd", ".toml", ".sh"}
DUPLICATED_WORK_PATHS = ("Harness/work/work/",)


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
        if any(part in {".git", "Binaries", "Intermediate", "Saved", "DerivedDataCache"} for part in path.parts):
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

    cycle_files = sorted(path for path in (harness / "work" / "cycles").glob("*.md") if path.name != ".gitkeep")
    if cycle_files:
        warnings.append({"path": "Harness/work/cycles/", "message": f"cycle_logs_present:{len(cycle_files)}"})
    task_files = sorted(
        path
        for path in (harness / "work" / "tasks").glob("*.md")
        if path.name not in {"README.md", "task.example.md"}
    )
    if task_files:
        warnings.append({"path": "Harness/work/tasks/", "message": f"real_task_records_present:{len(task_files)}"})

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
