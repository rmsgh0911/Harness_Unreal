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
KIND_PRIORITY = {"preferred": 0, "snapshot": 1, "index": 2, "task": 3, "cycle": 4, "doc": 5, "archive": 6}


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


def _section_metadata(body: str) -> dict:
    supersedes: list[str] = []
    invalidated = False
    collecting_supersedes = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Invalidated:"):
            invalidated = stripped.removeprefix("- Invalidated:").strip().casefold() in {"true", "yes", "1"}
            collecting_supersedes = False
        elif stripped.startswith("- Supersedes:"):
            value = stripped.removeprefix("- Supersedes:").strip().strip("`")
            if value:
                supersedes.append(value)
            collecting_supersedes = True
        elif collecting_supersedes and line.startswith("  - "):
            supersedes.append(stripped[2:].strip().strip("`"))
        elif stripped and not stripped.startswith("#"):
            collecting_supersedes = False
    return {"invalidated": invalidated, "supersedes": supersedes}


def _reference_keys(path: str, heading: str) -> set[str]:
    return {f"{path}#{heading}".casefold(), f"#{heading}".casefold(), heading.casefold()}


def _superseded_key(value: str, source_path: str) -> str:
    cleaned = value.strip().strip("`")
    markdown_link = re.fullmatch(r"\[[^\]]+\]\(([^)]+)\)", cleaned)
    if markdown_link:
        cleaned = markdown_link.group(1)
    if cleaned.startswith("#"):
        cleaned = source_path + cleaned
    return cleaned.replace("\\", "/").casefold()


def _path_kind(root: Path, path: Path) -> str:
    relative = rel(path, root)
    if relative in {"Harness/work/state.md", "Harness/work/next.md"}:
        return "snapshot"
    if relative.startswith("Harness/index/"):
        return "index"
    if relative.startswith("Harness/work/tasks/"):
        return "task"
    if relative.startswith("Harness/work/cycles/"):
        return "cycle"
    if relative.startswith("Harness/work/archive/"):
        return "archive"
    return "doc"


def _candidate_files(root: Path, preferred_paths: list[Path] | None = None) -> list[tuple[str, Path]]:
    harness = harness_dir(root)
    config = load_json(harness / "config" / "docs.json", {}) or {}
    candidates: list[tuple[str, Path]] = []
    for value in preferred_paths or []:
        candidate = value if value.is_absolute() else root / value
        try:
            candidate.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.name not in EXCLUDED_NAMES:
            candidates.append((_path_kind(root, candidate), candidate))
    for relative in ["Harness/work/state.md", "Harness/work/next.md"]:
        path = root / relative
        if path.exists():
            candidates.append(("snapshot", path))
    for path in sorted((harness / "index").glob("*.md")):
        candidates.append(("index", path))
    for folder, kind in [("tasks", "task"), ("cycles", "cycle")]:
        base = harness / "work" / folder
        if base.exists():
            candidates.extend((kind, path) for path in sorted(base.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    doc_roots_value = config.get("doc_roots", [])
    for doc_root in doc_roots_value if isinstance(doc_roots_value, list) else []:
        base = root / doc_root
        if base.exists() and base.is_dir():
            candidates.extend(("doc", path) for path in sorted(base.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    archive = harness / "work" / "archive"
    if archive.exists():
        candidates.extend(("archive", path) for path in sorted(archive.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    unique: dict[str, tuple[str, Path]] = {}
    for kind, path in candidates:
        unique.setdefault(str(path.resolve()).casefold(), (kind, path))
    return list(unique.values())


def build_knowledge(
    root: Path,
    query: str = "",
    limit: int = 8,
    max_files: int = 200,
    preferred_paths: list[Path] | None = None,
) -> dict:
    all_candidates = _candidate_files(root, preferred_paths=preferred_paths)
    candidates = all_candidates[:max_files]
    counts: dict[str, int] = {}
    all_counts: dict[str, int] = {}
    for kind, _ in all_candidates:
        all_counts[kind] = all_counts.get(kind, 0) + 1
    matches: list[dict] = []
    records: list[dict] = []
    text_truncated_files: list[str] = []
    for kind, path in candidates:
        counts[kind] = counts.get(kind, 0) + 1
        full_text = read_text(path)
        if len(full_text) > 50000:
            text_truncated_files.append(rel(path, root))
        text = full_text[:50000]
        for heading, line, body in _sections(text):
            relative = rel(path, root)
            metadata = _section_metadata(body)
            record = {
                "kind": kind,
                "path": relative,
                "section": heading,
                "line": line,
                "reference": f"{relative}#{heading}",
                **metadata,
            }
            records.append(record)
            if query.strip():
                score = _score(query, f"{heading}\n{body}")
                if score:
                    matches.append({**record, "score": score})
    replacements: dict[str, str] = {}
    for record in records:
        for value in record["supersedes"]:
            replacements[_superseded_key(value, record["path"])] = record["reference"]
    for item in matches:
        replacement = next((replacements[key] for key in _reference_keys(item["path"], item["section"]) if key in replacements), "")
        item["status"] = "invalidated" if item["invalidated"] else ("superseded" if replacement else "current")
        item["replacement"] = replacement
    matches.sort(key=lambda item: (-item["score"], KIND_PRIORITY.get(item["kind"], 99), item["path"], item["line"]))
    omitted_counts = {
        kind: count - counts.get(kind, 0)
        for kind, count in sorted(all_counts.items())
        if count - counts.get(kind, 0) > 0
    }
    omitted_files = max(0, len(all_candidates) - len(candidates))
    return {
        "root": str(root),
        "query": query,
        "candidate_files": len(all_candidates),
        "scanned_files": len(candidates),
        "truncated": omitted_files > 0 or bool(text_truncated_files),
        "omitted_files": omitted_files,
        "omitted_counts": omitted_counts,
        "text_truncated_files": text_truncated_files,
        "broader_query": f"rerun with --max-files {max(max_files + 50, max_files * 2)}" if omitted_files else "",
        "counts": counts,
        "matches": matches[:limit],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Knowledge",
        f"- Root: {report['root']}",
        f"- Query: {report['query'] or 'inventory only'}",
        f"- Scanned files: {report['scanned_files']} of {report['candidate_files']}",
        "- Sources: " + (", ".join(f"{kind}={count}" for kind, count in sorted(report["counts"].items())) or "none"),
        "",
        "Relevant Existing Material:",
    ]
    if report["matches"]:
        for item in report["matches"]:
            replacement = f" -> {item['replacement']}" if item.get("replacement") else ""
            lines.append(f"- [{item['kind']}/{item['status']}] {item['path']}:{item['line']} > {item['section']}{replacement}")
    else:
        lines.append("- none")
    if report["omitted_files"]:
        omitted = ", ".join(f"{kind}={count}" for kind, count in report["omitted_counts"].items())
        lines.extend(["", f"Omitted by file bound: {report['omitted_files']} ({omitted})", f"Broader query: {report['broader_query']}"])
    if report["text_truncated_files"]:
        lines.extend(["", f"Files truncated at 50,000 characters: {len(report['text_truncated_files'])}"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search existing Harness material without reading the whole repository.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--query", default="", help="Request or feature text used to rank existing material.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum matching sections to return.")
    parser.add_argument("--max-files", type=int, default=200, help="Maximum known Harness files to inspect.")
    parser.add_argument("--path", action="append", type=Path, default=[], help="Prioritize an explicit repository-relative file. Can be repeated.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if args.limit < 1 or args.max_files < 1:
        parser.error("--limit and --max-files must be positive")
    root = find_project_root(args.root)
    report = build_knowledge(root, query=args.query, limit=args.limit, max_files=args.max_files, preferred_paths=args.path)
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
