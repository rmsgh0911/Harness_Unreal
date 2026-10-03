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
- Add a stable kebab-case alias to `harness_cli.py`; every registered standard tool must remain reachable through the managed runtime.

## Recommended Shape

```powershell
& Harness\harness.ps1 <tool-alias> --help
& Harness\harness.ps1 <tool-alias> --json
& Harness\harness.ps1 <tool-alias> --write
```

Keep tools small. Split them by purpose when they grow.

## Primary Commands

Agents should remember the portable launcher and this small command surface first. Use `& Harness\harness.ps1` in Windows PowerShell or `sh Harness/harness.sh` on POSIX. Keep `harness.cmd` to fixed-token convenience calls because CMD reparses free-form metacharacters before the wrapper can preserve them:

- `context`: start with a request-scoped briefing.
- `cycle`: record repeated or task-scoped work.
- `iteration-status`: inspect cycle budget and evidence before continuing repeated work.
- `project-fill`: preview or explicitly fill first-project configuration.
- `init-plan`: summarize first-install or migration work.
- `field-check`: run field-proven structure and wrapper checks.
- `readiness`: check first-install or post-update project connection quality.
- `verify`: run the standard finish gate.
- `sensitive`: scan long-lived Harness text without printing matched sensitive values.
- `local-gate`: run the local no-CI finish gate for solo or private Gitea work.
- `memory-review`: check whether finished work has compact memory candidates before staging.
- `handoff`: prepare a compact handoff for another worker or session.
- `subagent`: build a bounded, read-only delegation packet for a registered helper role.
- `update`: update an older Harness install without overwriting project-owned data.

`harness_cli.py` is the thin router behind the launchers. Every registered standard tool has an alias so a bootstrapped project never needs PATH Python. Existing direct Python entry points remain supported for automation that already supplies an interpreter.

Other tools in this folder are supporting diagnostics, migration helpers, optional project features, or implementation details used by the primary commands.

## Standard Tools

- `harness_context.py`: prints a short Harness briefing with scoped Korean/English update routing, active local rules, request-related next items, and index sections; use `--all-next` for the full list.
- `harness_doctor.py`: checks Harness document, config, and manifest consistency.
- `harness_docs_check.py`: checks `Harness/docs` and `docs.json` discovery / reading policy.
- `harness_scan.py`: summarizes Unreal project structure and `project.json` candidates.
- `harness_archive.py`: previews or transactionally archives completed task/cycle records by task ID, or date-named cycle files older than a month with `--before YYYY-MM`; validates the month and rolls back failed moves.
- `harness_work.py`: previews a verified task closeout, then with `--write` atomically marks it completed and archives its task/cycle pair; failed archive work restores the original task bytes.
- `harness_iteration_status.py`: reports cycle progress, budget, verification/evidence gaps, and repeated unresolved work without writing files.
- `harness_update_plan.py`: uses manifest ownership and an optional hash receipt for conservative two-way or precise three-way planning; it preserves project-owned paths, reports newline-only text differences without changing bytes, rejects escaping paths, and writes a receipt only after resolved changes and successful verification.
- `harness_knowledge.py`: searches retained material with explicit/current files before historical docs and archives, marks invalidated/superseded sections, and reports omitted source counts when file or text bounds truncate the search.
- `harness_memory.py`: maintains optional daily JSONL memory shards with UUID entries, review status changes, pruning diagnostics, and a rebuildable local SQLite search cache.
- `harness_memory_review.py`: reviews changed paths and memory shard health before staging; suggests reusable memory candidate categories without writing files.
- `harness_cycle.py`: creates cycle log entries with durable exact/upper-bound budget mode plus optional claim, evidence, revision, artifact, scope, acceptance, invalidation, and supersession metadata; writes only with `--write`. Use `--task` and `--worker` for parallel work.
- `harness_diff_guard.py`: checks changed files and Unreal risk signals.
- `harness_field_check.py`: checks field-proven operating risks, suspicious doc text artifacts, nested Harness review copies, Unreal Python wrapper hints, and optional branch-ref alignment.
- `harness_handoff.py`: creates a compact handoff with staged/unstaged/untracked groups, context warnings, and explicit omission counts. Unavailable Git is unknown, not a clean tree. `--write` accepts only project-contained, non-linked destinations and never replaces a non-handoff file.
- `harness_subagent.py`: validates and pins provider-neutral helper contracts; prints bounded, redacted evidence with caller provenance, warnings and staged scope/content readiness. It does not search broad history, enforce a runtime sandbox, execute supplied verification, spawn an agent or write files. See `Harness/agents/README.md` for collection limits.

  Commit scope defaults to 256 paths independently of status and patch limits. Increase it with `--max-staged-paths` up to 4096 and bind a retry to the previous `git.snapshot_id` using `--expected-snapshot`.
- `harness_local_gate.py`: runs the no-CI local finish gate: tool tests, read-only Harness Python cache inventory, `harness_verify_all.py --skip-tool-tests`, optional strict release check, conflict/untracked reporting, and separate staged/unstaged diff checks and stats. Cache removal requires `--cleanup-caches`.
- `harness_local_gate.py` includes the read-only memory review step, so projects without server CI still see commit/push memory candidates before diff checks.
- `harness_verify_all.py`: runs lightweight standard checks before finishing work; real project mode requires complete build configuration.
- `harness_sensitive_check.py`: blocks high-confidence credentials, reports ambiguous assignments as warnings, and supports hash-only expiring exceptions.
- `harness_artifact_check.py`: validates project-owned generated-artifact provenance, safe relative paths, matching revisions, output existence/SHA-256, evidence scope, and acceptance; strict mode also blocks pending or missing-source warnings.
- `harness_release_check.py`: checks template packaging hygiene, including generated files and symlinks, before copying or zipping.
- `harness_release_pack.py`: previews or atomically writes a clean template ZIP; protected output paths and strict hygiene failures block writes.
- `harness_template_manifest.py`: verifies or explicitly refreshes the deterministic release inventory, hashes, and ownership rules.
- `harness_migration_audit.py`: audits an older Harness project before migration.
- `harness_state_check.py`: checks whether state/next/tasks/cycles are compact, stale, or mixed with completed history; findings have stable IDs and `--strict` blocks new or expired warning debt from `record_policy.json`.
- `harness_progress_check.py`: enforces the four-section, 40-line Progress dashboard contract.
- `harness_progress_html.py`: writes the tracked `Harness/Progress_index.html` viewer only when `Harness/Progress.md` exists; `--serve` exposes only those two regular, non-linked files on localhost (double-click `Harness/Progress_view.cmd` for the same result). Missing viewer/source fails before starting a server.
- `harness_python_check.py`: checks Python 3 availability and Unreal Python candidates.
- `harness_init_plan.py`: summarizes preservation, fill, and verification work for initialization or migration.
- `harness_docs_index.py`: indexes project doc headings to reduce reading scope.
- `harness_index_check.py`: checks whether `Harness/index/` stays compact, complete, and fresh enough.
- `harness_project_fill.py`: creates `project.json` candidates and fills blank fields only with `--write`.
- `harness_project_readiness.py`: checks post-install or post-update project connection quality; `harness_verify_all.py` includes it.
- `harness_cycle_summary.py`: summarizes recent cycle logs.
- `harness_unreal_risk.py`: extracts Unreal-specific risk signals from changed files.
- `harness_unreal_script.py`: checks Unreal Python script readiness and command; runs only with `--run`. Missing readiness or failed execution exits nonzero. Reports readiness, execution, and acceptance separately; exit zero from Unreal is process evidence, not proof of asset/UI acceptance. With `--json`, engine output goes to stderr so stdout remains machine-readable.
- `harness_tool_usage.py`: static reference audit of the tools; flags low-reference consolidation candidates as the tool count grows.

## Field-Proven Tool Choices

- Use the launcher `context` command before editing so the agent reads targeted state instead of rediscovering the whole project.
- Use launcher `unreal-script --script <file> --run` for scripts that import `unreal`; plain CPython is only enough for ordinary Python helpers.
- Use launcher `iteration-status` before continuing long repeated work so cycle budgets, missing verification, and stop conditions stay visible.
- Use launcher `knowledge --query "<request>"` after migrations or context handoffs to route into retained docs and cycle records without broad scans.
- Use `knowledge --history --query "<request>"` for all retained execution records, optionally filtered by `--task`, `--decision`, or `--since YYYY-MM-DD`. `knowledge --rebuild-history` explicitly refreshes its disposable SQLite token index; ordinary queries remain read-only. See `Harness/data/README.md` for character budgets, cache/source guarantees, and recovery limits.
- Use launcher `memory --query "<request>" --limit 5` for short reviewed lessons; treat results as routing hints, not final evidence.
- Use launcher `memory-review` before staging when a task is being summarized, committed, or pushed; add memory only for reusable decisions, routing hints, or project rules.
- Use launcher `verify` as the standard finish gate, then inspect `git diff --stat` to confirm scope.

Examples:

```powershell
& Harness\harness.ps1 context
& Harness\harness.ps1 context --request "Improve lock-on input flow"
& Harness\harness.ps1 context --request "Improve lock-on input flow" --no-memory
& Harness\harness.ps1 context --request "Improve lock-on input flow" --memory-limit 5
& Harness\harness.ps1 context --request "Improve lock-on input flow" --all-next
& Harness\harness.ps1 doctor --json
& Harness\harness.ps1 docs-check --json
& Harness\harness.ps1 scan --json
& Harness\harness.ps1 archive --task completed-task
& Harness\harness.ps1 archive --task completed-task --archive
& Harness\harness.ps1 close --task completed-task
& Harness\harness.ps1 close --task completed-task --write
& Harness\harness.ps1 iteration-status --request "up to 5 cycles" --task input-fix
& Harness\harness.ps1 update --target C:\Path\To\OlderProject
& Harness\harness.ps1 update --target C:\Path\To\OlderProject --apply-missing --stage-review C:\Temp\HarnessReview
& Harness\harness.ps1 update --target C:\Path\To\OlderProject --stage-review C:\Temp\HarnessReview --overwrite-stage
& Harness\harness.ps1 update --target C:\Path\To\OlderProject --accept-receipt
& Harness\harness.ps1 knowledge --query "lock-on input"
& Harness\harness.ps1 knowledge --query "lock-on input" --path Harness/work/tasks/input-fix.md
& Harness\harness.ps1 memory --add --title "UMG PIE visibility" --body "AddToViewport in BeginPlay is PIE-only." --tags unreal,umg,pie --source Harness/docs/AgentFieldGuide.md
& Harness\harness.ps1 memory --validate
& Harness\harness.ps1 memory --doctor
& Harness\harness.ps1 memory --promote 00000000-0000-4000-8000-000000000001
& Harness\harness.ps1 memory --prune
& Harness\harness.ps1 memory --query "widget visible PIE" --limit 5
& Harness\harness.ps1 memory --rebuild
& Harness\harness.ps1 memory-review
& Harness\harness.ps1 cycle "Input fix" --changed "..." --verified "..." --remaining "..."
& Harness\harness.ps1 cycle "Parallel input fix" --task input-fix --worker Codex --changed "..." --verified "..."
& Harness\harness.ps1 cycle "Iteration 2" --task input-fix --max-cycles 5 --budget-mode upper_bound --decision continue --success-criterion "Lock-on remains stable"
& Harness\harness.ps1 cycle "UI acceptance" --task input-fix --max-cycles 5 --budget-mode upper_bound --decision continue --claim "Lock-on marker renders" --evidence-kind render --artifact Saved/Screenshots/lock-on.png --input-revision abc123 --artifact-revision abc123 --scope "PIE 1920x1080" --acceptance passed
& Harness\harness.ps1 diff-guard
& Harness\harness.ps1 state-check --strict
& Harness\harness.ps1 field-check --branches main feature/login release/1.2
& Harness\harness.ps1 handoff --request "Continue lock-on work"
& Harness\harness.ps1 subagent --list
& Harness\harness.ps1 subagent --role current-status --request "Summarize lock-on work" --task input-fix
& Harness\harness.ps1 subagent --role commit-explainer --request "Prepare the requested commit" --verification "Harness verify passed" --include-staged-patch
& Harness\harness.ps1 local-gate
& Harness\harness.ps1 local-gate --cleanup-caches
& Harness\harness.ps1 verify
& Harness\harness.ps1 sensitive
& Harness\harness.ps1 artifacts
& Harness\harness.ps1 artifacts --strict
& Harness\harness.ps1 sensitive --strict
& Harness\harness.ps1 manifest
& Harness\harness.ps1 manifest --write
& Harness\harness.ps1 local-gate --release
& Harness\harness.ps1 release-check --json
& Harness\harness.ps1 release-check --strict
& Harness\harness.ps1 release-pack --json
& Harness\harness.ps1 release-pack --write
& Harness\harness.ps1 migration-audit --target C:\Path\To\OldProject
& Harness\harness.ps1 state-check --root C:\Path\To\Project
& Harness\harness.ps1 progress-check --json
& Harness\harness.ps1 progress --write
& Harness\harness.ps1 progress --serve
& Harness\harness.ps1 python-check
& Harness\harness.ps1 init-plan
& Harness\harness.ps1 docs-index
& Harness\harness.ps1 index-check --json
& Harness\harness.ps1 project-fill --json
& Harness\harness.ps1 readiness
& Harness\harness.ps1 readiness --after-update
& Harness\harness.ps1 cycle-summary
& Harness\harness.ps1 unreal-risk
& Harness\harness.ps1 unreal-script --script Harness/scripts/unreal/verify_project.py
& Harness\harness.ps1 tool-usage
```

For a deliberately retained manual merge, add `--resolutions <review.json>` to receipt acceptance. The JSON object maps each reviewed path to `local_sha256`, `upstream_sha256`, and `reason`; obtain both hashes from a fresh update plan. Receipt acceptance rejects stale acknowledgements and changes made during verification. Standard launcher checks preserve existing registered custom tools; new project tools should use `Harness/scripts/project/`.

If `python` resolves to the Microsoft Store alias on Windows, use the real Python 3 executable, set `HARNESS_PYTHON`, or run `& Harness\harness.ps1 bootstrap` to create an isolated managed runtime. The bootstrap is a native-launcher command, so it works without Python; it is explicit, checksum-verifies its pinned uv 0.12.18 installer, disables Python Install Manager automatic installation during normal command probes, and never modifies PATH or the Windows Python registry. Use `bootstrap --status` for a network-free check. Closed networks must provide uv 0.12.18 through `HARNESS_UV` plus an environment-based Python mirror or preseeded `UV_CACHE_DIR` / `HARNESS_UV_CACHE_DIR`.

## Template Quality Checks

The launcher `doctor` command also checks:

- every standard tool is registered in `tool_manifest.json`
- each tool `verify` command references the real tool path
- core `project.json` fields are filled after migration into a real Unreal project
- no generated `__pycache__` or `*.pyc` files remain under `Harness/scripts/`

Launcher `release-pack --write` requires the reviewed manifest inventory, runs the strict release check itself, and refuses to write when the manifest is missing, invalid, or stale. It also rejects non-ZIP outputs, source-file overwrites, outputs under `Harness/`, and symlinks. ZIP creation uses fixed entry metadata, sorted entries, uncompressed storage, and a temporary sibling file, so identical content produces identical bytes across supported platforms and a failed write does not corrupt an existing package. `--force` bypasses non-manifest hygiene failures only; manifest integrity and output-path safety remain unforceable. The package excludes `.git/`, `.claude/`, `Harness/.runtime/`, `Harness/temp/`, generated caches, generated handoff files, and real task, cycle, and archive records.
