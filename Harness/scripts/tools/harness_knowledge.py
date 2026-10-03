"""Search existing Harness docs, indexes, and work records as compact routing evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, normalize_search_token, read_text, rel


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./+\-]{2,}|[\uac00-\ud7a3]{2,}")
STOP_WORDS = {"the", "and", "for", "from", "with", "this", "that", "project", "task", "work", "harness", "프로젝트", "작업", "해줘", "해주세요"}
EXCLUDED_NAMES = {"README.md", "task.example.md", ".gitkeep"}
KIND_PRIORITY = {"preferred": 0, "snapshot": 1, "index": 2, "task": 3, "cycle": 4, "doc": 5, "archive": 6}
HISTORY_VERSION = "4"


def _history_snapshot(root: Path) -> tuple[str, list[tuple[Path, bytes]]]:
    files = []
    base = harness_dir(root) / "work"
    for folder in ("tasks", "cycles", "archive"):
        files.extend(path for path in (base / folder).rglob("*.md")
                     if path.name not in EXCLUDED_NAMES and path.name != "index.md")
    digest = hashlib.sha256()
    snapshot = []
    for path in sorted(set(files)):
        path.resolve().relative_to(root.resolve())
        data = path.read_bytes()
        digest.update(rel(path, root).encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
        snapshot.append((path, data))
    return digest.hexdigest(), snapshot


def _history_records(root: Path, snapshot: list[tuple[Path, bytes]]) -> list[dict]:
    from harness_cycle_summary import parse_cycle_text

    records = []
    for path, data in snapshot:
        text = data.decode("utf-8-sig")
        relative = rel(path, root)
        is_cycle = "cycles" in Path(relative).parts
        cycle_rows = parse_cycle_text(text, path)["sections"] if is_cycle else []
        cycles = {item["line"]: item for item in cycle_rows}
        if is_cycle:
            # Nested headings belong to the enclosing cycle, not a discarded section.
            lines = text.splitlines()
            sections = [(item["title"], item["line"], "\n".join(lines[item["line"] - 1:
                         cycle_rows[index + 1]["line"] - 1 if index + 1 < len(cycle_rows) else len(lines)]))
                        for index, item in enumerate(cycle_rows)]
        else:
            sections = _sections(text)
        task_dates = dict(re.findall(r"^- (Started|Updated):\s*(.+)$", text, re.MULTILINE))
        task_date = task_dates.get("Updated", task_dates.get("Started", "")).strip()
        for heading, line, body in sections:
            if is_cycle and line not in cycles:
                continue
            cycle = cycles.get(line, {})
            metadata = {"invalidated": cycle.get("invalidated", False), "supersedes": cycle.get("supersedes", [])} if is_cycle else _section_metadata(body)
            records.append({
                "kind": "cycle" if is_cycle else "task", "archived": "/archive/" in relative,
                "task": path.stem, "path": relative, "line": line, "section": heading,
                "reference": f"{relative}#{heading}", "recorded_at": cycle.get("recorded_at", task_date),
                "decision": cycle.get("decision", ""), "evidence_status": cycle.get("evidence_status", "legacy_unknown"),
                "input_revision": cycle.get("input_revision", ""), "artifacts": cycle.get("artifacts", []),
                "evidence_commands": cycle.get("evidence_commands", []),
                "evidence_exit_codes": cycle.get("evidence_exit_codes", []),
                "body": body, **metadata,
            })
    _apply_replacements(records)
    return records


def _apply_replacements(records: list[dict]) -> None:
    from harness_cycle_summary import EVIDENCE_GAP_STATUSES
    replacements = {}
    exact = {record["reference"].casefold() for record in records}
    archived_aliases: dict[str, set[str]] = {}
    for record in records:
        match = re.fullmatch(r"Harness/work/archive/[^/]+/(tasks|cycles)/(.+)", record["path"])
        if match:
            alias = f"Harness/work/{match[1]}/{match[2]}#{record['section']}".casefold()
            archived_aliases.setdefault(alias, set()).add(record["reference"].casefold())
    for record in records:
        if not record["invalidated"] and record.get("evidence_status") not in EVIDENCE_GAP_STATUSES:
            for value in record["supersedes"]:
                key = _superseded_key(value, record["path"])
                aliases = archived_aliases.get(key, set())
                if key not in exact and len(aliases) == 1:
                    key = next(iter(aliases))
                replacements[key] = record["reference"]
    for item in records:
        replacement = next((replacements[key] for key in sorted(_reference_keys(item["path"], item["section"])) if key in replacements), "")
        item["status"] = ("invalidated" if item["invalidated"] else "superseded" if replacement else
                          "evidence_gap" if item.get("evidence_status") in EVIDENCE_GAP_STATUSES else "current")
        item["replacement"] = replacement


def _history_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def _decode_history_record(payload: str) -> dict:
    record = json.loads(payload)
    text_keys = ("kind", "task", "path", "section", "reference", "recorded_at", "decision", "evidence_status", "body", "status", "replacement")
    if not isinstance(record, dict) or any(not isinstance(record.get(key), str) for key in text_keys):
        raise ValueError("invalid cached history record")
    if not isinstance(record.get("line"), int) or record["line"] < 1:
        raise ValueError("invalid cached history location")
    return record


def rebuild_history(root: Path) -> dict:
    """Explicitly replace a disposable history index; never modify work records."""
    fingerprint, snapshot = _history_snapshot(root)
    records = _history_records(root, snapshot)
    destination = root / "Harness/data/history.sqlite"
    destination.resolve().relative_to(root.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".history-", suffix=".sqlite", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript("""
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE history_record (id INTEGER PRIMARY KEY, task TEXT, decision TEXT, payload TEXT);
            CREATE TABLE history_token (token TEXT, record_id INTEGER, PRIMARY KEY(token, record_id));
            CREATE INDEX history_task ON history_record(task, decision);
        """)
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", [("version", HISTORY_VERSION), ("fingerprint", fingerprint)])
        for number, record in enumerate(records):
            connection.execute("INSERT INTO history_record VALUES (?, ?, ?, ?)",
                               (number, record["task"], record["decision"], json.dumps(record, ensure_ascii=False)))
            connection.executemany("INSERT INTO history_token VALUES (?, ?)",
                                   [(token, number) for token in _tokens(record["task"] + " " + record["body"])])
        connection.commit()
        connection.close()
        if _history_snapshot(root)[0] != fingerprint:
            raise ValueError("history changed during rebuild; retry from a stable snapshot")
        os.replace(temporary, destination)
    finally:
        connection.close()
        temporary.unlink(missing_ok=True)
    return {"ok": True, "database": rel(destination, root), "indexed": len(records), "source_files": len(snapshot)}


def build_history(root: Path, query: str = "", limit: int = 8, max_chars: int = 4000,
                  task: str = "", decision: str = "", since: str = "") -> dict:
    from harness_memory import budget_results, result_chars

    if limit < 1 or max_chars < 200:
        raise ValueError("history requires limit >= 1 and max_chars >= 200")
    if since:
        datetime.strptime(since, "%Y-%m-%d")
    report = {"ok": True, "query": query, "source": "markdown", "cache_status": "absent", "warnings": [], "errors": []}
    try:
        fingerprint, snapshot = _history_snapshot(root)
        records = None
        cache = root / "Harness/data/history.sqlite"
        if cache.exists():
            connection = None
            try:
                cache.resolve().relative_to(root.resolve())
                connection = _history_connection(cache)
                connection.execute("BEGIN")
                metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                if metadata.get("version") == HISTORY_VERSION and metadata.get("fingerprint") == fingerprint:
                    filters, values = [], []
                    if task:
                        filters.append("task = ?")
                        values.append(task)
                    if decision:
                        filters.append("decision = ?")
                        values.append(decision)
                    tokens = sorted(_tokens(query))
                    if tokens:
                        filters.append("id IN (SELECT record_id FROM history_token WHERE token IN (" + ",".join("?" for _ in tokens) + "))")
                        values.extend(tokens)
                    where = " WHERE " + " AND ".join(filters) if filters else ""
                    records = [_decode_history_record(row[0]) for row in connection.execute("SELECT payload FROM history_record" + where, values)]
                    report.update(source="sqlite", cache_status="current")
                else:
                    report["cache_status"] = "stale"
            except (sqlite3.Error, ValueError, OSError):
                report["cache_status"] = "unavailable"
                records = None
            finally:
                if connection is not None:
                    connection.close()
        if records is None:
            records = _history_records(root, snapshot)
        if report["cache_status"] in {"stale", "unavailable"}:
            report["warnings"].append("history cache is stale or unavailable; read Markdown without changing the cache; use knowledge --rebuild-history")
        if _history_snapshot(root)[0] != fingerprint:
            raise ValueError("history changed during query; retry from a stable snapshot")
        matches = []
        for record in records:
            if task and record["task"] != task or decision and record["decision"] != decision:
                continue
            if since:
                try:
                    recorded_date = datetime.strptime(record["recorded_at"][:10], "%Y-%m-%d").date()
                except ValueError:
                    continue
                if recorded_date < datetime.strptime(since, "%Y-%m-%d").date():
                    continue
            score = _score(query, record["task"] + " " + record["body"]) if query.strip() else 1
            if score:
                matches.append(dict(record, score=score))
        matches.sort(key=lambda item: (item["status"] != "current", -item["score"], item["path"], item["line"]))
        results = budget_results(matches, limit, max_chars)
        report.update(source_files=len(snapshot), matched_count=len(matches), omitted_count=len(matches) - len(results),
                      count=len(results), results=results, result_chars=result_chars(results), max_chars=max_chars)
    except (OSError, UnicodeError, ValueError) as exc:
        report.update(ok=False, results=[], count=0, errors=[str(exc)])
    return report


def _tokens(text: str) -> set[str]:
    raw = TOKEN_PATTERN.findall(text)
    # Keep identifiers/paths searchable as a whole, and words at punctuation boundaries.
    parts = [part for token in raw for part in re.findall(r"[A-Za-z0-9_]{2,}|[가-힣]{2,}", token)]
    tokens = {normalize_search_token(token.strip("._/-")) for token in [*raw, *parts]}
    return {token for token in tokens if token and token not in STOP_WORDS}


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
    return {f"{path}#{heading}".casefold()}


def _superseded_key(value: str, source_path: str) -> str:
    cleaned = value.strip().strip("`")
    markdown_link = re.fullmatch(r"\[[^\]]+\]\(([^)]+)\)", cleaned)
    if markdown_link:
        cleaned = markdown_link.group(1)
    if cleaned.startswith("#"):
        cleaned = source_path + cleaned
    elif "#" not in cleaned:
        cleaned = source_path + "#" + cleaned
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
        if not isinstance(doc_root, str):
            continue
        base = root / doc_root
        base.resolve().relative_to(root.resolve())
        if base.exists() and base.is_dir():
            candidates.extend(("doc", path) for path in sorted(base.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    archive = harness / "work" / "archive"
    if archive.exists():
        candidates.extend(("archive", path) for path in sorted(archive.rglob("*.md")) if path.name not in EXCLUDED_NAMES)
    unique: dict[str, tuple[str, Path]] = {}
    for kind, path in candidates:
        path.resolve().relative_to(root.resolve())
        unique.setdefault(os.path.normcase(str(path.resolve())), (kind, path))
    return list(unique.values())


def build_knowledge(
    root: Path,
    query: str = "",
    limit: int = 8,
    max_files: int = 200,
    preferred_paths: list[Path] | None = None,
) -> dict:
    if limit < 1 or max_files < 1:
        raise ValueError("limit and max_files must be positive")
    errors = []
    try:
        all_candidates = _candidate_files(root, preferred_paths=preferred_paths)
    except (OSError, ValueError) as exc:
        all_candidates = []
        errors.append(str(exc))
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
        try:
            full_text = read_text(path)
        except (OSError, UnicodeError) as exc:
            errors.append(f"{rel(path, root)}: cannot read UTF-8 source: {exc}")
            continue
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
    _apply_replacements(records)
    status_by_ref = {item["reference"]: item for item in records}
    for item in matches:
        item.update((key, status_by_ref[item["reference"]][key]) for key in ("status", "replacement"))
    matches.sort(key=lambda item: (item["status"] != "current", -item["score"], KIND_PRIORITY.get(item["kind"], 99), item["path"], item["line"]))
    omitted_counts = {
        kind: count - counts.get(kind, 0)
        for kind, count in sorted(all_counts.items())
        if count - counts.get(kind, 0) > 0
    }
    omitted_files = max(0, len(all_candidates) - len(candidates))
    return {
        "root": str(root),
        "ok": not errors,
        "errors": errors,
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
    if report.get("errors"):
        lines.extend(["", "Source errors:", *(f"- {error}" for error in report["errors"][:5])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search existing Harness material without reading the whole repository.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--query", default="", help="Request or feature text used to rank existing material.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum matching sections to return.")
    parser.add_argument("--max-files", type=int, default=200, help="Maximum known Harness files to inspect.")
    parser.add_argument("--path", action="append", type=Path, default=[], help="Prioritize an explicit repository-relative file. Can be repeated.")
    parser.add_argument("--history", action="store_true", help="Search all task/cycle/archive records independently of the documentation file bound.")
    parser.add_argument("--rebuild-history", action="store_true", help="Explicitly rebuild the disposable history.sqlite index from work records.")
    parser.add_argument("--task", default="", help="Exact task ID filter for --history.")
    parser.add_argument("--decision", choices=["", "continue", "stop_success", "stop_blocked"], default="", help="Decision filter for --history.")
    parser.add_argument("--since", default="", help="Include history recorded on or after YYYY-MM-DD; undated records are excluded.")
    parser.add_argument("--max-chars", type=int, default=4000, help="Compact JSON history result character budget, excluding diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    if args.limit < 1 or args.max_files < 1:
        parser.error("--limit and --max-files must be positive")
    root = find_project_root(args.root)
    if (args.task or args.decision or args.since) and not args.history:
        parser.error("--task, --decision and --since require --history")
    if args.history or args.rebuild_history:
        try:
            report = rebuild_history(root) if args.rebuild_history else build_history(
                root, args.query, args.limit, args.max_chars, args.task, args.decision, args.since)
        except (OSError, UnicodeError, ValueError, sqlite3.Error) as exc:
            report = {"ok": False, "errors": [str(exc)]}
        print(dump_json(report))
        raise SystemExit(0 if report["ok"] else 1)
    report = build_knowledge(root, query=args.query, limit=args.limit, max_files=args.max_files, preferred_paths=args.path)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
