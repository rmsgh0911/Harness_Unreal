"""Search existing Harness docs, indexes, and work records as compact routing evidence."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, normalize_search_token, read_text, rel


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./+\-]{2,}|[\uac00-\ud7a3]{2,}")
STOP_WORDS = {"the", "and", "for", "from", "with", "this", "that", "project", "task", "work", "harness", "프로젝트", "작업", "해줘", "해주세요"}
EXCLUDED_NAMES = {"README.md", "task.example.md", ".gitkeep"}


def _tokens(text: str) -> set[str]:
    tokens = {normalize_search_token(token) for token in TOKEN_PATTERN.findall(text)}
    return {token for token in tokens if token not in STOP_WORDS}


def _score(query: str, text: str) -> int:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0
    text_tokens = _tokens(text)
    return 3 * len(query_tokens & text_tokens)


def _sections(text: str) -> list[tuple[str, int, str]]:
    sections: list[tuple[str, int, str]] = []
    heading = "document"
    start = 1
    body: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            if body:
                sections.append((heading, start, "\n".join(body)))
            heading = line.lstrip("#").strip() or "document"
            start = line_number
            body = [line]
        else:
            body.append(line)
    if body:
        sections.append((heading, start, "\n".join(body)))
    return sections


def _candidate_files(root: Path) -> list[tuple[str, Path]]:
    harness = harness_dir(root)
    config = load_json(harness / "config" / "docs.json", {}) or {}
    candidates: list[tuple[str, Path]] = []
    for relative in ["Harness/work/state.md", "Harness/work/next.md"]:
        path = root / relative
        if path.exists():
            candidates.append(("snapshot", path))
    for path in sorted((harness / "index").glob("*.md")):
        candidates.append(("index", path))
    for doc_root in config.get("doc_roots", []) if isinstance(config.get("doc_roots", []), list) else []:
        base = root / doc_root
        if base.exists() and base.is_dir():
            candidates.extend(("doc", path) for path in sorted(base.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    for folder, kind in [("tasks", "task"), ("cycles", "cycle"), ("archive", "archive")]:
        base = harness / "work" / folder
        if base.exists():
            candidates.extend((kind, path) for path in sorted(base.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    unique: dict[str, tuple[str, Path]] = {}
    for kind, path in candidates:
        unique.setdefault(str(path.resolve()).casefold(), (kind, path))
    return list(unique.values())


def build_knowledge(root: Path, query: str = "", limit: int = 8, max_files: int = 200) -> dict:
    all_candidates = _candidate_files(root)
    candidates = all_candidates[:max_files]
    counts: dict[str, int] = {}
    matches: list[dict] = []
    for kind, path in candidates:
        counts[kind] = counts.get(kind, 0) + 1
        if not query.strip():
            continue
        text = read_text(path)[:50000]
        for heading, line, body in _sections(text):
            score = _score(query, f"{heading}\n{body}")
            if score:
                matches.append({"kind": kind, "path": rel(path, root), "section": heading, "line": line, "score": score})
    matches.sort(key=lambda item: (-item["score"], item["path"], item["line"]))
    return {
        "root": str(root),
        "query": query,
        "scanned_files": len(candidates),
        "truncated": len(all_candidates) > max_files,
        "counts": counts,
        "matches": matches[:limit],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Knowledge",
        f"- Root: {report['root']}",
        f"- Query: {report['query'] or 'inventory only'}",
        f"- Scanned files: {report['scanned_files']}{'+' if report['truncated'] else ''}",
        "- Sources: " + (", ".join(f"{kind}={count}" for kind, count in sorted(report["counts"].items())) or "none"),
        "",
        "Relevant Existing Material:",
    ]
    lines.extend(f"- [{item['kind']}] {item['path']}:{item['line']} > {item['section']}" for item in report["matches"]) if report["matches"] else lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search existing Harness material without reading the whole repository.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--query", default="", help="Request or feature text used to rank existing material.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum matching sections to return.")
    parser.add_argument("--max-files", type=int, default=200, help="Maximum known Harness files to inspect.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    report = build_knowledge(root, query=args.query, limit=args.limit, max_files=args.max_files)
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
