"""Summarize recent Harness cycle logs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, read_text, rel, print_text_or_json


def parse_cycle_file(path: Path) -> dict:
    text = read_text(path)
    sections: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = {"title": line[3:].strip(), "changed": [], "verified": [], "remaining": []}
            sections.append(current)
            continue
        if not current:
            continue
        stripped = line.strip()
        for key, label in [("changed", "- 변경:"), ("verified", "- 검증:"), ("remaining", "- 남은 것:")]:
            if stripped.startswith(label):
                current[key].append(stripped.removeprefix(label).strip())
    return {"path": path, "sections": sections, "lines": len(text.splitlines())}


def build_summary(root: Path, limit: int = 5) -> dict:
    cycles = harness_dir(root) / "cycles"
    files = sorted((path for path in cycles.glob("*.md") if path.name != ".gitkeep"), reverse=True) if cycles.exists() else []
    selected = files[:limit]
    parsed = [parse_cycle_file(path) for path in selected]
    remaining: list[str] = []
    verified: list[str] = []
    changed: list[str] = []
    for item in parsed:
        for section in item["sections"]:
            changed.extend(value for value in section["changed"] if value and value != "작성 필요")
            verified.extend(value for value in section["verified"] if value and value != "작성 필요")
            remaining.extend(value for value in section["remaining"] if value and value not in {"없음", "작성 필요"})
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
    lines = [
        "Harness Cycle Summary",
        f"- Root: {summary['root']}",
        f"- Cycle files: {summary['file_count']}",
    ]
    lines.append("")
    lines.append("Selected:")
    lines.extend(f"- {item['path']}: {item['sections']} sections, {item['lines']} lines" for item in summary["selected"]) if summary["selected"] else lines.append("- none")
    for key, title in [("recent_changed", "Recent Changed"), ("recent_verified", "Recent Verified"), ("open_remaining", "Open Remaining")]:
        lines.extend(["", f"{title}:"])
        items = summary[key]
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize recent Harness cycle logs.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent cycle files to summarize.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    summary = build_summary(root, limit=args.limit)
    print_text_or_json(summary if args.json else format_text(summary), args.json)


if __name__ == "__main__":
    main()
