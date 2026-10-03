"""Maintain optional Harness memory using JSONL shards and a SQLite cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, normalize_search_token, rel


SCHEMA_VERSION = "3"
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
CREATE TABLE IF NOT EXISTS memory_token (
  token TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  PRIMARY KEY (token, entry_id)
);
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
    return [normalize_search_token(match.group(0)) for match in TOKEN_PATTERN.finditer(text)]


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ensure_layout(root: Path) -> None:
    for path in (data_dir(root), memory_dir(root), db_path(root)):
        require_local_path(root, path)
    memory_dir(root).mkdir(parents=True, exist_ok=True)
    gitkeep = memory_dir(root) / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def connect(root: Path, *, readonly: bool = False) -> sqlite3.Connection:
    path = db_path(root)
    require_local_path(root, path)
    if readonly:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 3000")
    return connection


def initialize_database(root: Path) -> dict:
    return rebuild_cache(root)


@contextmanager
def write_lock(root: Path):
    ensure_layout(root)
    path = data_dir(root) / ".memory.lock"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("memory writer lock exists; wait for the writer or review a stale .memory.lock before removing it") from exc
    os.close(descriptor)
    try:
        yield
    finally:
        path.unlink()


def atomic_bytes(path: Path, data: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".memory-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def commit_sources(root: Path, changes: dict[Path, bytes]) -> dict:
    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    promoted = []
    try:
        for path, data in changes.items():
            atomic_bytes(path, data)
            promoted.append(path)
        rebuilt = _rebuild_cache(root)
        if not rebuilt["ok"]:
            raise ValueError("memory rebuild rejected changed sources")
        return rebuilt
    except Exception:
        for path in reversed(promoted):
            if originals[path] is None:
                path.unlink()
            else:
                atomic_bytes(path, originals[path])
        raise


def validate_entry(raw: dict[str, Any], shard_path: str = "") -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("memory entry must be an object")
    for field in ("id", "created_at", "title", "body"):
        if not isinstance(raw.get(field), str):
            raise ValueError(f"memory entry {field} must be a string")
    entry_id = str(raw.get("id", "")).strip()
    if not entry_id:
        raise ValueError("memory entry missing id")
    try:
        entry_id = str(uuid.UUID(entry_id))
    except ValueError as exc:
        raise ValueError(f"invalid memory entry id: {entry_id}") from exc

    created_at = str(raw.get("created_at", "")).strip()
    if not created_at:
        raise ValueError(f"memory entry {entry_id} missing created_at")
    try:
        timestamp = datetime.fromisoformat(created_at)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise ValueError(f"memory entry {entry_id} has invalid created_at") from exc

    status = str(raw.get("status", "confirmed")).strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"memory entry {entry_id} has invalid status: {status}")

    title = str(raw.get("title", "")).strip()
    body = str(raw.get("body", "")).strip()
    if not title or not body:
        raise ValueError(f"memory entry {entry_id} requires title and body")
    if not isinstance(raw.get("tags", []), (list, str)) or (isinstance(raw.get("tags"), list) and any(not isinstance(tag, str) for tag in raw["tags"])):
        raise ValueError(f"memory entry {entry_id} tags must be strings")
    if not isinstance(raw.get("source", ""), str):
        raise ValueError(f"memory entry {entry_id} source must be a string")

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
    require_local_path(root, base)
    if not base.exists():
        return []
    paths = sorted(path for path in base.glob("*.jsonl") if path.is_file())
    for path in paths:
        require_local_path(root, path)
    return paths


def require_local_path(root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"memory path escapes project root: {path}") from exc


def source_fingerprint(root: Path) -> str:
    """Bind a cache to exact shard names and bytes, including deletions."""
    digest = hashlib.sha256()
    for path in iter_shards(root):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def cache_status(root: Path) -> dict:
    status = {"exists": db_path(root).exists(), "path": rel(db_path(root), root), "status": "absent", "stale": False}
    if not status["exists"]:
        return status
    try:
        connection = connect(root, readonly=True)
        try:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        finally:
            connection.close()
        fingerprint = source_fingerprint(root)
        current = metadata.get("schema_version") == SCHEMA_VERSION and metadata.get("memory_fingerprint") == fingerprint
        status.update(status="current" if current else "stale", stale=not current, fingerprint=fingerprint)
    except (OSError, ValueError, sqlite3.Error):
        status.update(status="unavailable", stale=True)
    return status


def load_jsonl_entries(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen_ids: dict[str, str] = {}
    try:
        shards = iter_shards(root)
    except (OSError, ValueError) as exc:
        return [], [{"path": str(MEMORY_RELATIVE), "error": str(exc)}]
    for shard in shards:
        try:
            lines = shard.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append({"path": rel(shard, root), "error": f"cannot read UTF-8 memory shard: {exc}"})
            continue
        for line_number, line in enumerate(lines, start=1):
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


def upsert_entries(root: Path, entries: list[dict[str, Any]], replace: bool = False, fingerprint: str = "") -> None:
    descriptor, name = tempfile.mkstemp(prefix=".memory-cache-", suffix=".sqlite", dir=data_dir(root))
    os.close(descriptor)
    temporary = Path(name)
    connection = sqlite3.connect(temporary)
    try:
        if db_path(root).exists():
            original = None
            try:
                original = connect(root, readonly=True)
                original.backup(connection)
            except sqlite3.Error:
                pass  # Explicit rebuild may replace a damaged derived cache.
            finally:
                if original is not None:
                    original.close()
        # These are owned derived tables: repair incompatible old schemas too.
        connection.executescript("DROP TABLE IF EXISTS memory_token; DROP TABLE IF EXISTS memory_entry; DROP TABLE IF EXISTS metadata;")
        connection.executescript(DEFAULT_SCHEMA)
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
        connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", ("memory_fingerprint", fingerprint))
        connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", ("schema_version", SCHEMA_VERSION))
        connection.executemany("INSERT INTO memory_token(token, entry_id) VALUES (?, ?)",
                               [(token, entry["id"]) for entry in entries for token in set(_tokens(
                                   " ".join((entry["title"], entry["body"], " ".join(entry["tags"]), entry["source"]))))])
        connection.commit()
        connection.close()
        os.replace(temporary, db_path(root))
    finally:
        connection.close()
        if temporary.exists():
            temporary.unlink()


def rebuild_cache(root: Path) -> dict:
    with write_lock(root):
        return _rebuild_cache(root)


def _rebuild_cache(root: Path) -> dict:
    before = source_fingerprint(root)
    entries, errors = load_jsonl_entries(root)
    if errors:
        return {"ok": False, "database": rel(db_path(root), root), "indexed": 0, "errors": errors}
    if source_fingerprint(root) != before:
        return {"ok": False, "indexed": 0, "errors": [{"error": "memory changed during rebuild; retry from a stable snapshot"}]}
    upsert_entries(root, entries, replace=True, fingerprint=before)
    return {"ok": True, "database": rel(db_path(root), root), "indexed": len(entries), "errors": []}


def validate_memory(root: Path) -> dict:
    entries, errors = load_jsonl_entries(root)
    try:
        shards = [rel(path, root) for path in iter_shards(root)]
    except (OSError, ValueError):
        shards = []  # load_jsonl_entries already carries the actionable error.
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
    with write_lock(root):
        return _update_status(root, str(uuid.UUID(entry_id)), status)


def _update_status(root: Path, entry_id: str, status: str) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    validation = validate_memory(root)
    if not validation["ok"]:
        return {"ok": False, "updated": False, "errors": validation["errors"]}
    matches: list[tuple[Path, int, dict[str, Any], list[dict[str, Any]]]] = []
    errors: list[dict[str, str]] = []
    for shard in iter_shards(root):
        rows, shard_errors = _load_shard_json(shard)
        errors.extend(shard_errors)
        for index, row in enumerate(rows):
            raw = row.get("raw")
            if isinstance(raw, dict) and str(uuid.UUID(raw["id"])) == entry_id:
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
    data = ("\n".join(row["text"] for row in rows if row["text"] is not None) + "\n").encode("utf-8")
    rebuild = commit_sources(root, {shard: data})
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
    content_groups: dict[tuple[str, str], list[dict]] = {}

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
        content_groups.setdefault(key, []).append(entry)

    for group in content_groups.values():
        retained = max(group, key=lambda entry: (entry["status"] == "confirmed", _parse_iso(entry["created_at"]), entry["id"]))
        for entry in group:
            if entry["id"] != retained["id"]:
                findings.append({"kind": "duplicate_content", "id": entry["id"], "title": entry["title"], "first_id": retained["id"]})

    cache = cache_status(root)
    if cache["stale"]:
        findings.append({"kind": "stale_cache", "database": cache["path"], "message": "cache is stale or unavailable; query falls back to JSONL; run --rebuild"})

    return {
        "ok": not errors and not findings,
        "entries": len(entries),
        "errors": errors,
        "findings": findings,
        "cache": cache,
    }


def prune_memory(root: Path, args: argparse.Namespace) -> dict:
    if args.write:
        with write_lock(root):
            return _prune_memory(root, args)
    return _prune_memory(root, args)


def _prune_memory(root: Path, args: argparse.Namespace) -> dict:
    report = memory_doctor(root, draft_days=args.prune_draft_days, max_body_chars=args.prune_max_body_chars)
    removable_ids = [
        item["id"]
        for item in report["findings"]
        if item.get("kind") in {"stale_draft", "duplicate_content"} and item.get("id")
    ]
    removed: list[str] = []
    if args.write and removable_ids and not report["errors"]:
        remove_set = set(removable_ids)
        changes = {}
        for shard in iter_shards(root):
            rows, errors = _load_shard_json(shard)
            if errors:
                continue
            kept_lines: list[str] = []
            changed = False
            for row in rows:
                raw = row.get("raw")
                if isinstance(raw, dict) and str(uuid.UUID(raw["id"])) in remove_set:
                    removed.append(str(raw["id"]))
                    changed = True
                    continue
                if row["text"] is not None:
                    kept_lines.append(row["text"])
            if changed:
                changes[shard] = (("\n".join(kept_lines) + "\n") if kept_lines else "").encode("utf-8")
        commit_sources(root, changes)
    return {
        "ok": not report["errors"],
        "write": args.write,
        "candidates": removable_ids,
        "removed": removed,
        "doctor": report,
    }


def add_entry(root: Path, args: argparse.Namespace) -> dict:
    with write_lock(root):
        return _add_entry(root, args)


def _add_entry(root: Path, args: argparse.Namespace) -> dict:
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
    entries, errors = load_jsonl_entries(root)
    if errors:
        raise ValueError("invalid memory shards block additions; run --validate first")
    if any(existing["id"] == entry["id"] for existing in entries):
        raise ValueError(f"duplicate memory id: {entry['id']}")
    shard = memory_dir(root) / f"{_entry_date(entry['created_at'])}.jsonl"
    entry["shard_path"] = rel(shard, root)
    prior = shard.read_bytes() if shard.exists() else b""
    if prior and not prior.endswith(b"\n"):
        prior += b"\n"
    rebuilt = commit_sources(root, {shard: prior + (entry_to_json(entry) + "\n").encode("utf-8")})
    return {"ok": rebuilt["ok"], "entry": entry, "shard": rel(shard, root), "database": rel(db_path(root), root), "errors": rebuilt.get("errors", [])}


def rows_from_cache(root: Path, include_draft: bool, query_tokens: list[str] | None = None, fingerprint: str = "") -> list[dict[str, Any]]:
    if not db_path(root).exists():
        return []
    statuses = ("confirmed", "draft") if include_draft else ("confirmed",)
    placeholders = ",".join("?" for _ in statuses)
    connection = connect(root, readonly=True)
    try:
        connection.execute("BEGIN")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if fingerprint and (metadata.get("memory_fingerprint") != fingerprint or metadata.get("schema_version") != SCHEMA_VERSION):
            raise ValueError("memory cache changed between freshness check and read")
        tokens = sorted(set(query_tokens or []))
        token_filter = ""
        if tokens:
            token_filter = " AND id IN (SELECT entry_id FROM memory_token WHERE token IN (" + ",".join("?" for _ in tokens) + "))"
        rows = connection.execute(
            f"""
            SELECT id, created_at, status, title, body, tags, source, shard_path
            FROM memory_entry
            WHERE status IN ({placeholders}) {token_filter}
            ORDER BY created_at DESC
            """,
            (*statuses, *tokens),
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


def candidate_entries(root: Path, include_draft: bool, query_tokens: list[str] | None = None) -> tuple[list[dict[str, Any]], str, list[dict[str, str]], dict]:
    cache = cache_status(root)
    if cache["status"] == "current":
        try:
            rows = rows_from_cache(root, include_draft, query_tokens, cache["fingerprint"])
            if source_fingerprint(root) == cache["fingerprint"] and not (data_dir(root) / ".memory.lock").exists():
                return rows, "sqlite", [], cache
            cache.update(status="stale", stale=True)
        except (OSError, ValueError, sqlite3.Error):
            cache.update(status="unavailable", stale=True)
    try:
        before = source_fingerprint(root)
        entries, errors = load_jsonl_entries(root)
        if source_fingerprint(root) != before or (data_dir(root) / ".memory.lock").exists():
            return [], "jsonl", [{"error": "memory changed or writer lock exists; retry after writer completion or reviewed recovery"}], cache
    except (OSError, ValueError) as exc:
        return [], "jsonl", [{"error": str(exc)}], cache
    if not include_draft:
        entries = [entry for entry in entries if entry["status"] == "confirmed"]
    return entries, "jsonl", errors, cache


def score_entry(entry: dict[str, Any], query_tokens: list[str]) -> int:
    query = set(query_tokens)
    return sum(weight * len(query.intersection(_tokens(value))) for weight, value in (
        (3, entry["title"]), (2, " ".join(entry["tags"])),
        (1, entry["body"]), (1, entry.get("source", "")),
    ))


def result_chars(results: list[dict]) -> int:
    """Character budget for compact JSON results, including keys and provenance."""
    return len(json.dumps(results, ensure_ascii=False, separators=(",", ":")))


def budget_results(ranked: list[dict], limit: int, max_chars: int) -> list[dict]:
    results = []
    for entry in ranked:
        if len(results) >= limit:
            break
        if result_chars(results + [entry]) <= max_chars:
            results.append(entry)
            continue
        shortened = dict(entry, body="", truncated=True)
        if result_chars(results + [shortened]) > max_chars:
            continue  # Never truncate identity, title, or provenance to force a fit.
        low, high = 0, len(entry["body"])
        while low < high:
            middle = (low + high + 1) // 2
            shortened["body"] = entry["body"][:middle]
            if result_chars(results + [shortened]) <= max_chars:
                low = middle
            else:
                high = middle - 1
        shortened["body"] = entry["body"][:low]
        results.append(shortened)
    return results


def query_memory(root: Path, args: argparse.Namespace) -> dict:
    if args.limit < 1 or args.max_chars < 200:
        raise ValueError("query requires limit >= 1 and max_chars >= 200")
    query_tokens = _tokens(args.query)
    entries, source, errors, cache = candidate_entries(root, args.include_draft, query_tokens)
    ranked: list[dict[str, Any]] = []
    for entry in entries:
        score = score_entry(entry, query_tokens) if query_tokens else 1
        if score > 0:
            item = dict(entry)
            item["score"] = score
            ranked.append(item)
    ranked.sort(key=lambda item: (item["score"], _parse_iso(item["created_at"]), item["id"]), reverse=True)
    trimmed = budget_results(ranked, args.limit, args.max_chars)
    return {
        "ok": not errors,
        "source": source,
        "cache": cache,
        "warnings": ["memory cache is stale or unavailable; used JSONL without changing the cache"] if cache["stale"] else [],
        "query": args.query,
        "count": len(trimmed),
        "candidate_count": len(entries),
        "matched_count": len(ranked),
        "omitted_count": len(ranked) - len(trimmed),
        "result_chars": result_chars(trimmed),
        "max_chars": args.max_chars,
        "budget_scope": "compact JSON results only; envelope and diagnostics excluded; not a token count",
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
        f"- Result budget: {report['result_chars']}/{report['max_chars']} characters; omitted: {report['omitted_count']}",
    ]
    if report["errors"]:
        lines.append("- Errors: " + str(len(report["errors"])))
    lines.extend(f"- Warning: {warning}" for warning in report.get("warnings", []))
    if report["results"]:
        lines.append("")
        lines.append("Relevant memory:")
        for item in report["results"]:
            tags = ",".join(item["tags"])
            suffix = f" [{tags}]" if tags else ""
            source = f" ({item['source']})" if item.get("source") else ""
            truncation = " [body truncated; open source]" if item.get("truncated") else ""
            lines.append(f"- {item['title']}{suffix}: {item['body']}{source}{truncation}")
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
    parser.add_argument("--max-chars", type=int, default=1600, help="Maximum compact JSON result characters including metadata (not total CLI output or tokens).")
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

    try:
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
    except (ValueError, OSError, sqlite3.Error) as exc:
        report = {"ok": False, "errors": [{"error": str(exc)}]}

    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report.get("ok", False) else 1)


if __name__ == "__main__":
    main()
