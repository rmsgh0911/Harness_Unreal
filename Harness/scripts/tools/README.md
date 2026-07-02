# Harness Tool Repository

This folder contains small CLI tools that agents may add to reduce repeated exploration, verification, summarization, or recording cost.

## Add A Tool When

- The same exploration, verification, summarization, or recording task is likely to repeat.
- The result can be shown as short text or JSON.
- Project-specific values can come from `Harness/config/project.json` or command-line arguments.
- The default behavior is read-only, and file writes require an explicit option.

## Avoid A Tool When

- It is a one-off temporary conversion.
- The work requires heavy judgment or refactoring.
- Reliable results require unstable Unreal Editor internal state.
- Adding an option to an existing script is enough.

## Registration Rules

When adding a tool, update `tool_manifest.json` with:

- `name`: tool name
- `path`: repository-root-relative path
- `purpose`: repeated cost the tool reduces
- `inputs`: main inputs
- `outputs`: main outputs
- `writes_files`: whether it writes files by default or only with explicit options
- `safe_by_default`: whether default execution is read-only and safe on failure
- `verify`: minimal verification command

## Recommended Shape

```powershell
python Harness/scripts/tools/example_tool.py --help
python Harness/scripts/tools/example_tool.py --json
python Harness/scripts/tools/example_tool.py --write
```

Keep tools small. Split them by purpose when they grow.

## Primary Commands

Agents should remember this small command surface first:

- `harness_context.py`: start with a request-scoped briefing.
- `harness_cycle.py`: record repeated or task-scoped work.
- `harness_verify_all.py`: run the standard finish gate.
- `harness_local_gate.py`: run the local no-CI finish gate for solo or private Gitea work.
- `harness_handoff.py`: prepare a compact handoff for another worker or session.
- `harness_update_plan.py`: update an older Harness install without overwriting project-owned data.

Other tools in this folder are supporting diagnostics, migration helpers, optional project features, or implementation details used by the primary commands.

## Standard Tools

- `harness_context.py`: prints a short Harness briefing with only request-related next items and index sections; use `--all-next` for the full list.
- `harness_doctor.py`: checks Harness document, config, and manifest consistency.
- `harness_docs_check.py`: checks `Harness/docs` and `docs.json` discovery / reading policy.
- `harness_scan.py`: summarizes Unreal project structure and `project.json` candidates.
- `harness_archive.py`: previews or transactionally archives completed task/cycle records by task ID, or date-named cycle files older than a month with `--before YYYY-MM`; validates the month and rolls back failed moves.
- `harness_iteration_status.py`: reports cycle progress, budget, verification gaps, and repeated unresolved work without writing files.
- `harness_update_plan.py`: compares a new template with an older project, preserves exact project-owned paths, rejects escaping plan paths, adds only missing files with an explicit option, and stages changed template files for review.
- `harness_knowledge.py`: searches retained docs, indexes, tasks, cycles, archives, state, and next files as bounded routing evidence.
- `harness_memory.py`: maintains optional daily JSONL memory shards with UUID entries, review status changes, pruning diagnostics, and a rebuildable local SQLite search cache.
- `harness_cycle.py`: creates cycle log entries; writes only with `--write`. Use `--task` and `--worker` for parallel work.
- `harness_diff_guard.py`: checks changed files and Unreal risk signals.
- `harness_field_check.py`: checks field-proven operating risks, suspicious doc text artifacts, nested Harness review copies, Unreal Python wrapper hints, and optional branch-ref alignment.
- `harness_handoff.py`: creates a minimal handoff brief for another worker or session.
- `harness_local_gate.py`: runs the no-CI local finish gate: tool tests, Harness Python cache cleanup, `harness_verify_all.py --skip-tool-tests`, optional strict release check, `git diff --check`, and `git diff --stat`.
- `harness_verify_all.py`: runs lightweight standard checks before finishing work; real project mode requires complete build configuration.
- `harness_release_check.py`: checks template packaging hygiene, including generated files and symlinks, before copying or zipping.
- `harness_release_pack.py`: previews or atomically writes a clean template ZIP; protected output paths and strict hygiene failures block writes.
- `harness_migration_audit.py`: audits an older Harness project before migration.
- `harness_state_check.py`: checks whether state/next/tasks/cycles are compact, stale, or mixed with completed history.
- `harness_progress_check.py`: enforces the four-section, 40-line Progress dashboard contract.
- `harness_progress_html.py`: writes the tracked `Harness/Progress_index.html` viewer for `Harness/Progress.md`, and with `--serve` hosts `Harness/` on localhost so the viewer fetches the live file (double-click `Harness/Progress_view.cmd` for the same result).
- `harness_python_check.py`: checks Python 3 availability and Unreal Python candidates.
- `harness_init_plan.py`: summarizes preservation, fill, and verification work for initialization or migration.
- `harness_docs_index.py`: indexes project doc headings to reduce reading scope.
- `harness_index_check.py`: checks whether `Harness/index/` stays compact, complete, and fresh enough.
- `harness_project_fill.py`: creates `project.json` candidates and fills blank fields only with `--write`.
- `harness_cycle_summary.py`: summarizes recent cycle logs.
- `harness_unreal_risk.py`: extracts Unreal-specific risk signals from changed files.
- `harness_unreal_script.py`: checks Unreal Python script readiness and command; runs only with `--run`.
- `harness_tool_usage.py`: static reference audit of the tools; flags low-reference consolidation candidates as the tool count grows.

## Field-Proven Tool Choices

- Use `harness_context.py` before editing so the agent reads targeted state instead of rediscovering the whole project.
- Use `harness_unreal_script.py --script <file> --run` for scripts that import `unreal`; plain CPython is only enough for ordinary Python helpers.
- Use `harness_iteration_status.py` before continuing long repeated work so cycle budgets, missing verification, and stop conditions stay visible.
- Use `harness_knowledge.py --query "<request>"` after migrations or context handoffs to route into retained docs and cycle records without broad scans.
- Use `harness_memory.py --query "<request>" --limit 5` for short reviewed lessons; treat results as routing hints, not final evidence.
- Use `harness_verify_all.py` as the standard finish gate, then inspect `git diff --stat` to confirm scope.

Examples:

```powershell
python Harness/scripts/tools/harness_context.py
python Harness/scripts/tools/harness_context.py --request "Improve lock-on input flow"
python Harness/scripts/tools/harness_context.py --request "Improve lock-on input flow" --no-memory
python Harness/scripts/tools/harness_context.py --request "Improve lock-on input flow" --memory-limit 5
python Harness/scripts/tools/harness_context.py --request "Improve lock-on input flow" --all-next
python Harness/scripts/tools/harness_doctor.py --json
python Harness/scripts/tools/harness_docs_check.py --json
python Harness/scripts/tools/harness_scan.py --json
python Harness/scripts/tools/harness_archive.py --task completed-task
python Harness/scripts/tools/harness_archive.py --task completed-task --archive
python Harness/scripts/tools/harness_iteration_status.py --request "up to 5 cycles" --task input-fix
python Harness/scripts/tools/harness_update_plan.py --target C:\Path\To\OlderProject
python Harness/scripts/tools/harness_update_plan.py --target C:\Path\To\OlderProject --apply-missing --stage-review C:\Temp\HarnessReview
python Harness/scripts/tools/harness_update_plan.py --target C:\Path\To\OlderProject --stage-review C:\Temp\HarnessReview --overwrite-stage
python Harness/scripts/tools/harness_knowledge.py --query "lock-on input"
python Harness/scripts/tools/harness_memory.py --add --title "UMG PIE visibility" --body "AddToViewport in BeginPlay is PIE-only." --tags unreal,umg,pie --source Harness/docs/AgentFieldGuide.md
python Harness/scripts/tools/harness_memory.py --validate
python Harness/scripts/tools/harness_memory.py --doctor
python Harness/scripts/tools/harness_memory.py --promote 00000000-0000-4000-8000-000000000001
python Harness/scripts/tools/harness_memory.py --prune
python Harness/scripts/tools/harness_memory.py --query "widget visible PIE" --limit 5
python Harness/scripts/tools/harness_memory.py --rebuild
python Harness/scripts/tools/harness_cycle.py "Input fix" --changed "..." --verified "..." --remaining "..."
python Harness/scripts/tools/harness_cycle.py "Parallel input fix" --task input-fix --worker Codex --changed "..." --verified "..."
python Harness/scripts/tools/harness_cycle.py "Iteration 2" --task input-fix --max-cycles 5 --decision continue --success-criterion "Lock-on remains stable"
python Harness/scripts/tools/harness_diff_guard.py
python Harness/scripts/tools/harness_field_check.py --branches main feature/login release/1.2
python Harness/scripts/tools/harness_handoff.py --request "Continue lock-on work"
python Harness/scripts/tools/harness_local_gate.py
python Harness/scripts/tools/harness_local_gate.py --release
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_release_check.py --json
python Harness/scripts/tools/harness_release_check.py --strict
python Harness/scripts/tools/harness_release_pack.py --json
python Harness/scripts/tools/harness_release_pack.py --write
python Harness/scripts/tools/harness_migration_audit.py --target C:\Path\To\OldProject
python Harness/scripts/tools/harness_state_check.py --target C:\Path\To\Project
python Harness/scripts/tools/harness_progress_check.py --json
python Harness/scripts/tools/harness_progress_html.py --write
python Harness/scripts/tools/harness_progress_html.py --serve
python Harness/scripts/tools/harness_python_check.py
python Harness/scripts/tools/harness_init_plan.py
python Harness/scripts/tools/harness_docs_index.py
python Harness/scripts/tools/harness_index_check.py --json
python Harness/scripts/tools/harness_project_fill.py --json
python Harness/scripts/tools/harness_cycle_summary.py
python Harness/scripts/tools/harness_unreal_risk.py
python Harness/scripts/tools/harness_unreal_script.py --script Harness/scripts/unreal/verify_project.py
```

If `python` resolves to the Microsoft Store alias on Windows, use the real Python 3 executable or the workspace runtime Python path.

## Template Quality Checks

`harness_doctor.py` also checks:

- every standard tool is registered in `tool_manifest.json`
- each tool `verify` command references the real tool path
- core `project.json` fields are filled after migration into a real Unreal project
- no generated `__pycache__` or `*.pyc` files remain under `Harness/scripts/`

`harness_release_pack.py --write` runs the strict release check itself and refuses to write on failure. It also rejects non-ZIP outputs, source-file overwrites, outputs under `Harness/`, and symlinks. ZIP creation uses a temporary sibling file so a failed write does not corrupt an existing package. `--force` bypasses hygiene failures only and is reserved for exceptional diagnostics. The package excludes `.git/`, `.claude/`, generated caches, generated handoff files, and real task, cycle, and archive records.
