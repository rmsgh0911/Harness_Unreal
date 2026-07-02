# Changelog

This file tracks changes to the reusable Harness_Unreal template itself.
Project-specific current status belongs in `Harness/Progress.md`, and detailed project work history belongs in `Harness/work/tasks/` or `Harness/work/cycles/`.

## Unreleased

- Added `template/gitea-ci.md` to document online Gitea, closed-network mirrored-action, and preinstalled-Python CI runner modes.
- Documented a no-Actions/no-runner Gitea mode with a local-only finish gate so solo projects are not treated as if CI passed implicitly.
- Added `template/project-ci.md` to separate portable Harness CI from real Unreal project build, commandlet, automation, and PIE verification tiers.
- Narrowed the documented daily tool surface to five primary commands and moved the rest into supporting diagnostics.
- Added a `**Last updated:** YYYY-MM-DD HH:MM:SS +09:00` header to `Harness/Progress.md`; `harness_progress_check.py` parses it and warns when missing. Worktree merge conflicts on this replace-in-place dashboard are resolved by keeping the newest-stamped block (documented in HARNESS.md), and the integrator now explicitly owns Progress.md consolidation.
- Added `harness_tool_usage.py`: a static reference audit that flags low-reference tools as consolidation candidates as the tool count grows past twenty.
- Split the single `test_structure_tools.py` into per-area `test_*.py` files sharing `_harness_test_base.py`, so a failing tool's tests are easy to locate; the suite still runs via `unittest discover`.
- Added `harness_archive.py --before YYYY-MM` to archive date-named cycle files (including worker-prefixed ones) into monthly folders; task-based archiving alone could never drain them.
- `harness_state_check.py` now warns when completed task records remain unarchived and includes the exact archive command in cycle-accumulation findings.
- `harness_release_check.py` ignores imported reference Harness copies (`Harness_*-work*/`, mirrored in `.gitignore`) so real-project material brought in for migration analysis does not fail template hygiene.
- `harness_update_plan.py` stages template scaffolding READMEs/examples inside project-owned directories as merge-review candidates instead of preserving them forever, and emits `Post-Apply Notes` for transitional states (unregistered new tools, new `Harness/data/` layer, Progress viewer).
- `harness_doctor.py` warns when `Harness/data/` exists but `.gitignore` lacks the SQLite cache exclusions.
- Documented version-specific upgrade notes (memory/data layer, archive modes, transitional doctor warnings, Progress viewer) in the template setup guide.
- `harness_verify_all.py` reports unreadable Python sources (for example Windows MAX_PATH overflows on deep Unreal project paths) as compile failures instead of crashing mid-verification.
- `harness_docs_check.py` warns when a `Harness/docs` root grows heavy with binary design exports (field evidence: 160+ MB of Figma exports), pointing at external doc roots or Git LFS.
- `harness_doctor.py` unregistered-tool warnings now say how to fix them, and stray non-tool files (for example `.cpp` sources) parked in `scripts/tools/` are flagged.
- `harness_field_check.py` warns when `Harness/scripts/unreal/` accumulates more than 25 scripts; finished one-off capture/export scripts should be deleted since Git history preserves them.
- `harness_update_plan.py` lists target-only tool registrations (`custom_manifest_entries`) and warns to re-merge them so a wholesale manifest replacement cannot silently drop custom tools.
- Reviewed memory shards are explicitly protected during upgrades: `Harness/data/memory/` is project-owned in the update plan and listed as preserve by the migration audit.
- Split template history from the project-facing progress dashboard.
- Keep `Harness/Progress.md` neutral in template mode so strict release hygiene can pass.
- Clarified install and update guidance for preserving project-owned state while tracking template changes here.
- Added optional daily JSONL memory shards with UUID entries and a rebuildable local SQLite cache.
- Documented private Gitea use of reviewed daily memory shards while keeping SQLite cache files local.
- Added memory shard validation, duplicate UUID detection, and bounded memory hints in `harness_context.py`.
- Added memory review operations (`--promote`, `--demote`), quality checks (`--doctor`), dry-run pruning (`--prune`), and context memory controls (`--no-memory`, `--memory-limit`).
- Added tracked `Harness/Progress_index.html` and `harness_progress_html.py` as a thin viewer for `Harness/Progress.md`.
- Changed the Progress dashboard to avoid embedded status snapshots and added release checks for the dynamic viewer marker.
- Added `--serve` to `harness_progress_html.py` and a double-click `Harness/Progress_view.cmd` launcher that host `Harness/` on localhost so the viewer fetches the live `Progress.md` (browsers block local `fetch()` over `file://`); the viewer now shows in-page guidance to start the local server.
- Added regression tests for previously untested tools (`harness_scan`, `harness_project_fill`, `harness_docs_index`, `harness_migration_audit`) to widen the tool safety net.
- Added a portable `.github/workflows/tests.yml` CI workflow that runs the tool tests and `harness_verify_all.py` on every push and pull request. It works on GitHub Actions and on Gitea Actions (Gitea reads `.github/workflows/` by default; it additionally needs Actions enabled and a registered act_runner).
- Added a repository-wide `.gitattributes` default (`* text=auto eol=lf`) so line endings stay deterministic for every text type (html, yml, jsonl, sql, and future types); Windows-native files (`*.cmd`, `*.ps1`, `*.bat`, source, config, `*.uproject`) keep CRLF.
- Cleaned up doubled backslashes in `build_verify.ps1` path literals; behavior is unchanged on Windows and now matches the rest of the codebase.
