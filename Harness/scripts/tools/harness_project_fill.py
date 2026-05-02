"""Generate or fill Harness/config/project.json from project structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, print_text_or_json, rel, write_text
from harness_scan import scan


def deep_fill(existing: dict, candidate: dict, overwrite: bool = False) -> dict:
    result = dict(existing)
    for key, value in candidate.items():
        if isinstance(value, dict):
            current = result.get(key, {})
            result[key] = deep_fill(current if isinstance(current, dict) else {}, value, overwrite=overwrite)
        elif overwrite or not result.get(key):
            result[key] = value
    return result


def candidate_from_scan(root: Path) -> dict:
    report = scan(root, include_assets=False)
    candidate = report["project_json_candidate"]
    current = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    return {
        "scan": report,
        "current": current,
        "candidate": candidate,
    }


def build_report(root: Path, write: bool = False, overwrite: bool = False) -> dict:
    data = candidate_from_scan(root)
    target = harness_dir(root) / "config" / "project.json"
    final = deep_fill(data["current"] if isinstance(data["current"], dict) else {}, data["candidate"], overwrite=overwrite)
    changed = final != data["current"]
    if write and changed:
        write_text(target, dump_json(final) + "\n")
    return {
        "root": str(root),
        "target": rel(target, root),
        "write": write,
        "overwrite": overwrite,
        "changed": changed,
        "status": "written" if write and changed else "dry_run" if not write else "unchanged",
        "candidate": data["candidate"],
        "merged": final,
        "scan_summary": {
            "uprojects": len(data["scan"]["uprojects"]),
            "modules": data["scan"]["source"]["modules"],
            "editor_targets": data["scan"]["source"]["editor_targets"],
            "game_targets": data["scan"]["source"]["game_targets"],
        },
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Project Fill",
        f"- Root: {report['root']}",
        f"- Target: {report['target']}",
        f"- Status: {report['status']}",
        f"- Changed: {report['changed']}",
        f"- UProject files: {report['scan_summary']['uprojects']}",
        f"- Modules: {', '.join(report['scan_summary']['modules']) or 'none'}",
        "",
        "Merged project.json:",
        dump_json(report["merged"]),
    ]
    if not report["write"]:
        lines.append("")
        lines.append("Dry run only. Add --write to update empty fields.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill empty Harness/config/project.json fields from project structure.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--write", action="store_true", help="Write merged values to Harness/config/project.json.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing candidate fields. Use with care.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, write=args.write, overwrite=args.overwrite)
    print_text_or_json(report if args.json else format_text(report), args.json)


if __name__ == "__main__":
    main()
