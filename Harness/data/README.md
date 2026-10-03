# Harness Data

This folder holds optional local memory support for Harness.

- `memory/*.jsonl` is the source of truth. Each line is one memory entry with a UUID.
- `harness.sqlite` is a local search cache rebuilt from JSONL shards and is not committed.
- `history.sqlite` is an optional derived task/cycle/archive search index. Markdown under `Harness/work/` remains authoritative; no command logs are automatically copied into memory.
- `schema.sql` documents the SQLite cache schema.
- `memory.example.jsonl` shows the JSONL shape without project-specific facts.

The memory layer is a routing aid, not a source of truth. Agents should use entries to find relevant code, docs, assets, logs, or verification output, then confirm against the actual project state.

For public templates, keep real `memory/*.jsonl` shards empty or absent. For private Gitea or other private project repositories, daily shards can be committed when their contents are reviewed and safe to share.

Memory can be used while `Harness/config/project.json` still has `template_mode: true`; the memory tool is independent of Unreal project configuration. Strict template packaging excludes real daily shards and SQLite cache files, so public template packages stay clean even if a private checkout has local memory.

Recommended private-repo flow:

```powershell
& Harness\harness.ps1 memory-review
& Harness\harness.ps1 memory --add --title "..." --body "..." --tags unreal,workflow
& Harness\harness.ps1 memory --validate
& Harness\harness.ps1 memory --rebuild
& Harness\harness.ps1 memory --query "<request>" --limit 5
```

Run the launcher's `memory-review` command before staging a requested commit or push. It is read-only: it checks changed paths and memory shard health, then points at possible reusable decisions, routing hints, or project rules. Add an entry only when that candidate will reduce future context loading.

## Search Contracts

- Memory queries match normalized words (including common Korean particles), weight titles/tags, exclude drafts by default, and report source/cache status. They are routing hints, not verified current facts.
- `--max-chars` bounds the compact JSON **results array**, including metadata, tags, and provenance; the diagnostic envelope and pretty-print whitespace are excluded. This is a character budget, not a model-token measurement. Long bodies carry `truncated: true`; oversized identity/provenance records are omitted. Inspect the source before relying on a truncated hint.
- `matched_count`, `omitted_count`, and `result_chars` make retrieval coverage and output cost visible. They do not prove a production token-saving percentage or semantic recall. Keep a project-specific query/expected-reference corpus when evaluating search quality.
- Cache freshness uses exact source names and byte hashes, including deletion and same-timestamp changes. Queries never create or repair a cache. Stale/corrupt caches fall back to original files with a warning; malformed sources report errors rather than becoming accepted evidence.
- `knowledge --query` is bounded documentation routing. `knowledge --history` searches all retained task/cycle/archive Markdown independently of that document/file bound; legacy unstructured records may have unknown evidence metadata. Deleted, never-recorded, or external execution logs cannot be recovered by the index.

```powershell
& Harness\harness.ps1 knowledge --history --query "retry failure" --limit 5 --max-chars 4000
& Harness\harness.ps1 knowledge --history --task input-fix --decision stop_success --since 2026-09-01
& Harness\harness.ps1 knowledge --rebuild-history
```

The history index uses exact normalized-token SQL candidate selection, not embeddings. Queries still read/hash all source bytes to guarantee freshness; this is not constant-time storage at very large scale. Date filtering uses the recorded calendar date and excludes undated records. Success labels describe recorded evidence only; they do not rerun past commands or prove the current code still passes.

## Writes And Recovery

Memory IDs must be canonicalizable UUIDs and timestamps must include a timezone. Duplicate IDs, invalid source shards, and concurrent Harness writers are rejected before source changes. Existing naive timestamps require a reviewed correction using the original timezone; no timezone is guessed during migration. Duplicate-content pruning retains a confirmed copy before any draft, then prefers the newest timestamp; always review the default prune preview before explicit `--write`.

Memory writes use a single `.memory.lock`, atomic per-file replacement, and source rollback when a handled cache-update error occurs. This is **not** a crash-durable multi-file transaction: external editors do not honor the lock, process/power loss can interrupt multi-shard pruning, and rollback needs writable storage. Keep reviewed shards under version control. After an interrupted write, first confirm no writer is running, inspect shard diffs and any temporary files, preserve needed data, remove only the confirmed stale lock, run `memory --validate`, and explicitly rebuild. Do not blindly delete locks or assume a cache is a backup. A history rebuild only replaces its own derived index and never changes Markdown.
