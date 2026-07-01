"""Maintain optional Harness memory using JSONL shards and a SQLite cache."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, rel


SCHEMA_VERSION = "1"
DATA_RELATIVE = Path("Harness") / "data"
MEMORY_RELATIVE = DATA_RELATIVE / "memory"
DB_RELATIVE = DATA_RELATIVE / "harness.sqlite"
SCHEMA_RELATIVE = DATA_RELATIVE / "schema.sql"
VALID_STATUSES = {"confirmed", "draft"}
TOKEN_PATTERN = re.compile(r"[\w가-힣]+", re.UNICODE)
DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_entry (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'draft')),
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  shard_path TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_memory_entry_status ON memory_entry(status);
CREATE INDEX IF NOT EXISTS idx_memory_entry_created_at ON memory_entry(created_at);
"""


def data_dir(root: Path) -> Path:
    return root / DATA_RELATIVE


def memory_dir(root: Path) -> Path:
    return root / MEMORY_RELATIVE


def db_path(root: Path) -> Path:
    return root / DB_RELATIVE


def schema_path(root: Path) -> Path:
    return root / SCHEMA_RELATIVE


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _entry_date(created_at: str) -> str:
    return datetime.fromisoformat(created_at).strftime("%Y-%m-%d")


def _split_tags(raw_tags: str | list[str]) -> list[str]:
    if isinstance(raw_tags, list):
        values = raw_tags
    else:
        values = re.split(r"[, ]+", raw_tags)
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _tags_text(tags: str | list[str]) -> str:
    return ",".join(_split_tags(tags))


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)]


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ensure_layout(root: Path) -> None:
    memory_dir(root).mkdir(parents=True, exist_ok=True)
    gitkeep = memory_dir(root) / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def connect(root: Path) -> sqlite3.Connection:
    path = db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 3000")
    return connection


def initialize_database(root: Path) -> dict:
    ensure_layout(root)
    schema_file = schema_path(root)
    schema = schema_file.read_text(encoding="utf-8") if schema_file.exists() else DEFAULT_SCHEMA
    connection = connect(root)
    try:
        connection.executescript(schema)
        connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        connection.commit()
    finally:
        connection.close()
    return {"ok": True, "database": rel(db_path(root), root), "memory_dir": rel(memory_dir(root), root)}


def validate_entry(raw: dict[str, Any], shard_path: str = "") -> dict[str, Any]:
    entry_id = str(raw.get("id", "")).strip()
    if not entry_id:
        raise ValueError("memory entry missing id")
    try:
        uuid.UUID(entry_id)
    except ValueError as exc:
        raise ValueError(f"invalid memory entry id: {entry_id}") from exc

    created_at = str(raw.get("created_at", "")).strip()
    if not created_at:
        raise ValueError(f"memory entry {entry_id} missing created_at")
    try:
        datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise ValueError(f"memory entry {entry_id} has invalid created_at") from exc

    status = str(raw.get("status", "confirmed")).strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"memory entry {entry_id} has invalid status: {status}")

    title = str(raw.get("title", "")).strip()
    body = str(raw.get("body", "")).strip()
    if not title or not body:
        raise ValueError(f"memory entry {entry_id} requires title and body")

    return {
        "id": entry_id,
        "created_at": created_at,
        "status": status,
        "title": title,
        "body": body,
        "tags": _split_tags(raw.get("tags", [])),
        "source": str(raw.get("source", "")).strip(),
        "shard_path": shard_path,
    }


def entry_to_json(entry: dict[str, Any]) -> str:
    payload = {
        "id": entry["id"],
        "created_at": entry["created_at"],
        "status": entry["status"],
        "title": entry["title"],
        "body": entry["body"],
        "tags": _split_tags(entry.get("tags", [])),
        "source": entry.get("source", ""),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def iter_shards(root: Path) -> list[Path]:
    base = memory_dir(root)
    if not base.exists():
        return []
    return sorted(path for path in base.glob("*.jsonl") if path.is_file())


def load_jsonl_entries(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen_ids: dict[str, str] = {}
    for shard in iter_shards(root):
        for line_number, line in enumerate(shard.read_text(encoding="utf-8-sig").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
                entry = validate_entry(raw, rel(shard, root))
                location = f"{rel(shard, root)}:{line_number}"
                prior = seen_ids.get(entry["id"])
                if prior:
                    errors.append({
                        "path": rel(shard, root),
                        "line": str(line_number),
                        "error": f"duplicate memory id {entry['id']} also seen at {prior}",
                    })
                    continue
                seen_ids[entry["id"]] = location
                entries.append(entry)
            except Exception as exc:  # noqa: BLE001
                errors.append({"path": rel(shard, root), "line": str(line_number), "error": str(exc)})
    return entries, errors


def upsert_entries(root: Path, entries: list[dict[str, Any]], replace: bool = False) -> None:
    initialize_database(root)
    connection = connect(root)
    try:
        if replace:
            connection.execute("DELETE FROM memory_entry")
        connection.executemany(
            """
            INSERT OR REPLACE INTO memory_entry
            (id, created_at, status, title, body, tags, source, shard_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entry["id"],
                    entry["created_at"],
                    entry["status"],
                    entry["title"],
                    entry["body"],
                    _tags_text(entry["tags"]),
                    entry["source"],
                    entry["shard_path"],
                )
                for entry in entries
            ],
        )
        connection.commit()
    finally:
        connection.close()


def rebuild_cache(root: Path) -> dict:
    entries, errors = load_jsonl_entries(root)
    if errors:
        return {"ok": False, "database": rel(db_path(root), root), "indexed": 0, "errors": errors}
    upsert_entries(root, entries, replace=True)
    return {"ok": True, "database": rel(db_path(root), root), "indexed": len(entries), "errors": []}


def validate_memory(root: Path) -> dict:
    entries, errors = load_jsonl_entries(root)
    shards = [rel(path, root) for path in iter_shards(root)]
    return {
        "ok": not errors,
        "entries": len(entries),
        "shards": shards,
        "errors": errors,
    }


def _load_shard_json(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            rows.append({"line_number": line_number, "raw": None, "text": line})
            continue
        try:
            rows.append({"line_number": line_number, "raw": json.loads(stripped), "text": line})
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": path.as_posix(), "line": str(line_number), "error": str(exc)})
    return rows, errors


def update_status(root: Path, entry_id: str, status: str) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    matches: list[tuple[Path, int, dict[str, Any], list[dict[str, Any]]]] = []
    errors: list[dict[str, str]] = []
    for shard in iter_shards(root):
        rows, shard_errors = _load_shard_json(shard)
        errors.extend(shard_errors)
        for index, row in enumerate(rows):
            raw = row.get("raw")
            if isinstance(raw, dict) and raw.get("id") == entry_id:
                matches.append((shard, index, raw, rows))
    if errors:
        return {"ok": False, "updated": False, "errors": errors}
    if not matches:
        return {"ok": False, "updated": False, "errors": [{"error": f"memory entry not found: {entry_id}"}]}
    if len(matches) > 1:
        return {"ok": False, "updated": False, "errors": [{"error": f"duplicate memory id blocks status update: {entry_id}"}]}

    shard, index, raw, rows = matches[0]
    before = raw.get("status", "")
    raw["status"] = status
    rows[index]["text"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    shard.write_text("\n".join(row["text"] for row in rows if row["text"] is not None) + "\n", encoding="utf-8")
    rebuild = rebuild_cache(root)
    return {
        "ok": rebuild["ok"],
        "updated": True,
        "id": entry_id,
        "from": before,
        "to": status,
        "shard": rel(shard, root),
        "rebuild": rebuild,
        "errors": rebuild.get("errors", []),
    }


def memory_doctor(root: Path, draft_days: int = 30, max_body_chars: int = 600) -> dict:
    entries, errors = load_jsonl_entries(root)
    now = datetime.now().astimezone()
    findings: list[dict[str, Any]] = []
    title_body_seen: dict[tuple[str, str], str] = {}

    for entry in entries:
        if len(entry["body"]) > max_body_chars:
            findings.append({"kind": "long_body", "id": entry["id"], "title": entry["title"], "length": len(entry["body"])})
        if entry["status"] == "draft":
            try:
                age_days = (now - _parse_iso(entry["created_at"])).days
            except ValueError:
                age_days = 0
            if age_days > draft_days:
                findings.append({"kind": "stale_draft", "id": entry["id"], "title": entry["title"], "age_days": age_days})
        source = entry.get("source", "")
        if source and not re.match(r"^[a-z]+://", source) and not (root / source).exists():
            findings.append({"kind": "missing_source", "id": entry["id"], "title": entry["title"], "source": source})
        key = (entry["title"].casefold(), entry["body"].casefold())
        prior = title_body_seen.get(key)
        if prior:
            findings.append({"kind": "duplicate_content", "id": entry["id"], "title": entry["title"], "first_id": prior})
        else:
            title_body_seen[key] = entry["id"]

    db = db_path(root)
    shards = iter_shards(root)
    stale_cache = False
    if db.exists() and shards:
        db_mtime = db.stat().st_mtime
        stale_cache = any(path.stat().st_mtime > db_mtime for path in shards)
        if stale_cache:
            findings.append({"kind": "stale_cache", "database": rel(db, root), "message": "run --rebuild"})

    return {
        "ok": not errors and not findings,
        "entries": len(entries),
        "errors": errors,
        "findings": findings,
        "cache": {
            "exists": db.exists(),
            "path": rel(db, root),
            "stale": stale_cache,
        },
    }


def prune_memory(root: Path, args: argparse.Namespace) -> dict:
    report = memory_doctor(root, draft_days=args.prune_draft_days, max_body_chars=args.prune_max_body_chars)
    removable_ids = [
        item["id"]
        for item in report["findings"]
        if item.get("kind") in {"stale_draft", "duplicate_content"} and item.get("id")
    ]
    removed: list[str] = []
    if args.write and removable_ids and not report["errors"]:
        remove_set = set(removable_ids)
        for shard in iter_shards(root):
            rows, errors = _load_shard_json(shard)
            if errors:
                continue
            kept_lines: list[str] = []
            changed = False
            for row in rows:
                raw = row.get("raw")
                if isinstance(raw, dict) and raw.get("id") in remove_set:
                    removed.append(str(raw["id"]))
                    changed = True
                    continue
                if row["text"] is not None:
                    kept_lines.append(row["text"])
            if changed:
                shard.write_text(("\n".join(kept_lines) + "\n") if kept_lines else "", encoding="utf-8")
        rebuild_cache(root)
    return {
        "ok": not report["errors"],
        "write": args.write,
        "candidates": removable_ids,
        "removed": removed,
        "doctor": report,
    }


def add_entry(root: Path, args: argparse.Namespace) -> dict:
    created_at = args.created_at or _now_iso()
    entry = validate_entry(
        {
            "id": args.id or str(uuid.uuid4()),
            "created_at": created_at,
            "status": args.status,
            "title": args.title,
            "body": args.body,
            "tags": _split_tags(args.tags or ""),
            "source": args.source or "",
        }
    )
    ensure_layout(root)
    shard = memory_dir(root) / f"{_entry_date(entry['created_at'])}.jsonl"
    entry["shard_path"] = rel(shard, root)
    with shard.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry_to_json(entry) + "\n")
    upsert_entries(root, [entry], replace=False)
    return {"ok": True, "entry": entry, "shard": rel(shard, root), "database": rel(db_path(root), root)}


def rows_from_cache(root: Path, include_draft: bool) -> list[dict[str, Any]]:
    if not db_path(root).exists():
        return []
    statuses = ("confirmed", "draft") if include_draft else ("confirmed",)
    placeholders = ",".join("?" for _ in statuses)
    connection = connect(root)
    try:
        rows = connection.execute(
            f"""
            SELECT id, created_at, status, title, body, tags, source, shard_path
            FROM memory_entry
            WHERE status IN ({placeholders})
            ORDER BY created_at DESC
            """,
            statuses,
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "title": row["title"],
            "body": row["body"],
            "tags": _split_tags(row["tags"]),
            "source": row["source"],
            "shard_path": row["shard_path"],
        }
        for row in rows
    ]


def candidate_entries(root: Path, include_draft: bool) -> tuple[list[dict[str, Any]], str, list[dict[str, str]]]:
    rows = rows_from_cache(root, include_draft)
    if rows:
        return rows, "sqlite", []
    entries, errors = load_jsonl_entries(root)
    if not include_draft:
        entries = [entry for entry in entries if entry["status"] == "confirmed"]
    return entries, "jsonl", errors


def score_entry(entry: dict[str, Any], query_tokens: list[str]) -> int:
    haystack = " ".join([
        entry["title"],
        entry["body"],
        " ".join(entry["tags"]),
        entry.get("source", ""),
    ]).casefold()
    score = 0
    for token in query_tokens:
        count = haystack.count(token)
        score += count
        if token in entry["title"].casefold():
            score += 2
        if token in " ".join(entry["tags"]).casefold():
            score += 1
    return score


def query_memory(root: Path, args: argparse.Namespace) -> dict:
    query_tokens = _tokens(args.query)
    entries, source, errors = candidate_entries(root, args.include_draft)
    ranked: list[dict[str, Any]] = []
    for entry in entries:
        score = score_entry(entry, query_tokens) if query_tokens else 1
        if score > 0:
            item = dict(entry)
            item["score"] = score
            ranked.append(item)
    ranked.sort(key=lambda item: (item["score"], item["created_at"]), reverse=True)
    results = ranked[:args.limit]
    total_chars = 0
    trimmed: list[dict[str, Any]] = []
    for entry in results:
        text_cost = len(entry["title"]) + len(entry["body"]) + len(entry.get("source", ""))
        if trimmed and total_chars + text_cost > args.max_chars:
            break
        total_chars += text_cost
        trimmed.append(entry)
    return {
        "ok": not errors,
        "source": source,
        "query": args.query,
        "count": len(trimmed),
        "results": trimmed,
        "errors": errors,
    }


def format_text(report: dict) -> str:
    if "results" not in report:
        return dump_json(report)
    lines = [
        "Harness Memory",
        f"- Source: {report['source']}",
        f"- Results: {report['count']}",
    ]
    if report["errors"]:
        lines.append("- Errors: " + str(len(report["errors"])))
    if report["results"]:
        lines.append("")
        lines.append("Relevant memory:")
        for item in report["results"]:
            tags = ",".join(item["tags"])
            suffix = f" [{tags}]" if tags else ""
            source = f" ({item['source']})" if item.get("source") else ""
            lines.append(f"- {item['title']}{suffix}: {item['body']}{source}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use optional Harness JSONL memory and SQLite cache.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--init", action="store_true", help="Create Harness/data layout and SQLite cache.")
    actions.add_argument("--validate", action="store_true", help="Validate memory/*.jsonl shards without writing files.")
    actions.add_argument("--rebuild", action="store_true", help="Rebuild SQLite cache from memory/*.jsonl shards.")
    actions.add_argument("--add", action="store_true", help="Append one memory entry to today's JSONL shard and cache it.")
    actions.add_argument("--promote", metavar="UUID", help="Change one memory entry from draft to confirmed.")
    actions.add_argument("--demote", metavar="UUID", help="Change one memory entry from confirmed to draft.")
    actions.add_argument("--doctor", action="store_true", help="Report memory quality issues without writing files.")
    actions.add_argument("--prune", action="store_true", help="Find stale draft and duplicate-content candidates; delete only with --write.")
    actions.add_argument("--query", default=None, help="Search memory entries.")
    parser.add_argument("--id", default="", help="Optional UUID for --add. Defaults to a generated UUID.")
    parser.add_argument("--created-at", default="", help="Optional ISO timestamp for --add.")
    parser.add_argument("--status", choices=sorted(VALID_STATUSES), default="confirmed", help="Entry status for --add.")
    parser.add_argument("--title", default="", help="Entry title for --add.")
    parser.add_argument("--body", default="", help="Entry body for --add.")
    parser.add_argument("--tags", default="", help="Comma or space separated tags for --add.")
    parser.add_argument("--source", default="", help="Optional source path or note for --add.")
    parser.add_argument("--include-draft", action="store_true", help="Include draft entries in --query.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum query results.")
    parser.add_argument("--max-chars", type=int, default=1600, help="Maximum approximate result characters.")
    parser.add_argument("--prune-draft-days", type=int, default=30, help="Draft age threshold for --doctor and --prune.")
    parser.add_argument("--prune-max-body-chars", type=int, default=600, help="Body length threshold for --doctor and --prune.")
    parser.add_argument("--write", action="store_true", help="Apply --prune deletions. Other write actions are explicit by action name.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    root = find_project_root(args.root)
    if args.add and (not args.title.strip() or not args.body.strip()):
        parser.error("--add requires --title and --body")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.max_chars < 200:
        parser.error("--max-chars must be at least 200")
    if args.prune_draft_days < 0:
        parser.error("--prune-draft-days must be non-negative")

    if args.init:
        report = initialize_database(root)
    elif args.validate:
        report = validate_memory(root)
    elif args.rebuild:
        report = rebuild_cache(root)
    elif args.add:
        report = add_entry(root, args)
    elif args.promote:
        report = update_status(root, args.promote, "confirmed")
    elif args.demote:
        report = update_status(root, args.demote, "draft")
    elif args.doctor:
        report = memory_doctor(root, draft_days=args.prune_draft_days, max_body_chars=args.prune_max_body_chars)
    elif args.prune:
        report = prune_memory(root, args)
    else:
        report = query_memory(root, args)

    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report.get("ok", False) else 1)


if __name__ == "__main__":
    main()
