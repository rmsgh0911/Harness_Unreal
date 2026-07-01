# Changelog

This file tracks changes to the reusable Harness_Unreal template itself.
Project-specific current status belongs in `Harness/Progress.md`, and detailed project work history belongs in `Harness/work/tasks/` or `Harness/work/cycles/`.

## Unreleased

- Split template history from the project-facing progress dashboard.
- Keep `Harness/Progress.md` neutral in template mode so strict release hygiene can pass.
- Clarified install and update guidance for preserving project-owned state while tracking template changes here.
- Added optional daily JSONL memory shards with UUID entries and a rebuildable local SQLite cache.
- Documented private Gitea use of reviewed daily memory shards while keeping SQLite cache files local.
- Added memory shard validation, duplicate UUID detection, and bounded memory hints in `harness_context.py`.
- Added memory review operations (`--promote`, `--demote`), quality checks (`--doctor`), dry-run pruning (`--prune`), and context memory controls (`--no-memory`, `--memory-limit`).
- Added tracked `Harness/Progress_index.html` and `harness_progress_html.py` as a thin viewer for `Harness/Progress.md`.
- Changed the Progress dashboard to avoid embedded status snapshots and added release checks for the dynamic viewer marker.
