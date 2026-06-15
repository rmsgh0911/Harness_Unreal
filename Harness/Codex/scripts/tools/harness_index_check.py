"""Check Harness/Codex/index files for compactness and basic freshness signals."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, read_text, rel


REQUIRED_INDEX_FILES = [
    "README.md",
    "project_index.md",
    "api_surface.md",
    "verification_map.md",
]
SOFT_LIMITS = {
    "project_index.md": 140,
    "api_surface.md": 140,
    "verification_map.md": 140,
    "README.md": 80,
}
HARD_LIMITS = {
    "project_index.md": 240,
    "api_surface.md": 240,
    "verification_map.md": 240,
    "README.md": 140,
}


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def build_report(root: Path) -> dict:
    index = harness_dir(root) / "index"
    warnings: list[dict] = []
    errors: list[dict] = []
    files: list[dict] = []

    if not index.exists():
        errors.append({"path": "Harness/Codex/index", "message": "missing"})
        return {"root": str(root), "ok": False, "files": [], "warnings": warnings, "errors": errors}

    for name in REQUIRED_INDEX_FILES:
        path = index / name
        text = read_text(path)
        lines = _line_count(text)
        item = {"path": rel(path, root), "exists": path.exists(), "lines": lines}
        files.append(item)
        if not path.exists():
            errors.append({"path": item["path"], "message": "missing"})
            continue
        if lines > SOFT_LIMITS[name]:
            warnings.append({"path": item["path"], "message": f"longer_than_soft_limit:{SOFT_LIMITS[name]}"})
        if lines > HARD_LIMITS[name]:
            errors.append({"path": item["path"], "message": f"longer_than_hard_limit:{HARD_LIMITS[name]}"})

    source_map = index / "source_map.json"
    if source_map.exists():
        project_index = index / "project_index.md"
        if project_index.exists() and source_map.stat().st_mtime < project_index.stat().st_mtime:
            warnings.append({"path": rel(source_map, root), "message": "older_than_project_index"})

    return {
        "root": str(root),
        "ok": not errors,
        "files": files,
        "warnings": warnings,
        "errors": errors,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Index Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
    ]
    lines.append("")
    lines.append("Files:")
    lines.extend(f"- {item['path']}: {item['lines']} lines" for item in report["files"]) if report["files"] else lines.append("- none")
    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["warnings"])
    if report["errors"]:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["errors"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness/Codex/index compactness and required files.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
