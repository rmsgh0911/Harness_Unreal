"""Summarize recent Harness cycle logs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, find_project_root, print_text_or_json, read_text, rel


def parse_cycle_file(path: Path) -> dict:
    text = read_text(path)
    sections: list[dict] = []
    current: dict | None = None
    current_key: str | None = None
    labels = {"Changed": "changed", "Verified": "verified", "Remaining": "remaining"}
    for line in text.splitlines():
        if line.startswith("## "):
            current = {"title": line[3:].strip(), "worker": "", "changed": [], "verified": [], "remaining": []}
            sections.append(current)
            current_key = None
            continue
        if not current:
            continue
        stripped = line.strip()
        if stripped.startswith("- Worker:"):
            current["worker"] = stripped.removeprefix("- Worker:").strip()
            continue
        matched = False
        for label, key in labels.items():
            prefix = f"- {label}:"
            if stripped.startswith(prefix):
                current[key].append(stripped.removeprefix(prefix).strip())
                current_key = key
                matched = True
                break
        if not matched and current_key and stripped.startswith("- "):
            current[current_key].append(stripped[2:].strip())
    return {"path": path, "sections": sections, "lines": len(text.splitlines())}


def build_summary(root: Path, limit: int = 5) -> dict:
    cycles = cycles_dir(root)
    files = sorted(
        (path for path in cycles.glob("*.md") if path.name != ".gitkeep"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if cycles.exists() else []
    parsed = [parse_cycle_file(path) for path in files[:limit]]
    changed: list[str] = []
    verified: list[str] = []
    remaining: list[str] = []
    for item in parsed:
        for section in item["sections"]:
            changed.extend(value for value in section["changed"] if value and value != "record needed")
            verified.extend(value for value in section["verified"] if value and value != "record needed")
            remaining.extend(value for value in section["remaining"] if value and value not in {"none", "record needed"})
    return {
        "root": str(root),
        "cycle_dir_exists": cycles.exists(),
        "file_count": len(files),
        "selected": [{"path": rel(item["path"], root), "sections": len(item["sections"]), "lines": item["lines"]} for item in parsed],
        "recent_changed": changed[:12],
        "recent_verified": verified[:12],
        "open_remaining": remaining[:12],
    }


def format_text(summary: dict) -> str:
    lines = ["Harness Cycle Summary", f"- Root: {summary['root']}", f"- Cycle files: {summary['file_count']}", "", "Selected:"]
    lines.extend(f"- {item['path']}: {item['sections']} sections, {item['lines']} lines" for item in summary["selected"]) if summary["selected"] else lines.append("- none")
    for key, title in [("recent_changed", "Recent Changed"), ("recent_verified", "Recent Verified"), ("open_remaining", "Open Remaining")]:
        lines.extend(["", f"{title}:"])
        lines.extend(f"- {item}" for item in summary[key]) if summary[key] else lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize recently modified Harness cycle logs.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recently modified cycle files to summarize.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    summary = build_summary(root, limit=args.limit)
    print_text_or_json(summary if args.json else format_text(summary), args.json)


if __name__ == "__main__":
    main()
