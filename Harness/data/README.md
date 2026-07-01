# Harness Data

This folder holds optional local memory support for Harness.

- `memory/*.jsonl` is the source of truth. Each line is one memory entry with a UUID.
- `harness.sqlite` is a local search cache rebuilt from JSONL shards and is not committed.
- `schema.sql` documents the SQLite cache schema.
- `memory.example.jsonl` shows the JSONL shape without project-specific facts.

The memory layer is a routing aid, not a source of truth. Agents should use entries to find relevant code, docs, assets, logs, or verification output, then confirm against the actual project state.

For public templates, keep real `memory/*.jsonl` shards empty or absent. For private Gitea or other private project repositories, daily shards can be committed when their contents are reviewed and safe to share.

Memory can be used while `Harness/config/project.json` still has `template_mode: true`; the memory tool is independent of Unreal project configuration. Strict template packaging excludes real daily shards and SQLite cache files, so public template packages stay clean even if a private checkout has local memory.

Recommended private-repo flow:

```powershell
python Harness/scripts/tools/harness_memory.py --add --title "..." --body "..." --tags unreal,workflow
python Harness/scripts/tools/harness_memory.py --validate
python Harness/scripts/tools/harness_memory.py --rebuild
python Harness/scripts/tools/harness_memory.py --query "<request>" --limit 5
```
