"""Index Harness project documents without reading them in full."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, load_json, read_text, rel, print_text_or_json


def markdown_headings(text: str, max_headings: int) -> list[dict]:
    headings: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped.lstrip("#").strip()
        if title:
            headings.append({"line": line_number, "level": level, "title": title})
        if len(headings) >= max_headings:
            break
    return headings


def build_index(root: Path, max_files: int = 80, max_headings: int = 12) -> dict:
    config = load_json(harness_dir(root) / "config" / "docs.json", {}) or {}
    doc_roots = config.get("doc_roots", [])
    files: list[dict] = []
    truncated = False
    for doc_root in doc_roots if isinstance(doc_roots, list) else []:
        base = root / doc_root
        if not isinstance(doc_root, str) or not base.exists() or not base.is_dir():
            continue
        for path in sorted(base.glob("**/*.md")):
            if len(files) >= max_files:
                truncated = True
                break
            text = read_text(path)
            headings = markdown_headings(text, max_headings)
            files.append(
                {
                    "path": rel(path, root),
                    "title": headings[0]["title"] if headings else "",
                    "headings": headings,
                    "lines": len(text.splitlines()) if text else 0,
                    "chars": len(text),
                }
            )
        if truncated:
            break
    return {
        "root": str(root),
        "doc_roots": doc_roots,
        "file_count": len(files),
        "truncated": truncated,
        "files": files,
    }


def format_text(index: dict) -> str:
    lines = [
        "Harness Docs Index",
        f"- Root: {index['root']}",
        f"- Doc roots: {', '.join(index['doc_roots']) if index['doc_roots'] else 'none'}",
        f"- Markdown files: {index['file_count']}{'+' if index['truncated'] else ''}",
    ]
    if index["files"]:
        lines.append("")
        lines.append("Documents:")
        for item in index["files"]:
            lines.append(f"- {item['path']}: {item['title'] or 'no title'} ({item['lines']} lines)")
            for heading in item["headings"][1:5]:
                indent = "  " if heading["level"] > 1 else ""
                lines.append(f"  {indent}- {heading['title']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Harness docs by headings to reduce document-reading cost.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--max-files", type=int, default=80, help="Maximum markdown files to index.")
    parser.add_argument("--max-headings", type=int, default=12, help="Maximum headings per file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    index = build_index(root, max_files=args.max_files, max_headings=args.max_headings)
    print_text_or_json(index if args.json else format_text(index), args.json)


if __name__ == "__main__":
    main()
