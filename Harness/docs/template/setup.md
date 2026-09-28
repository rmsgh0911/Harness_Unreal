# Harness Template Setup

Use this guide when copying the template into an Unreal Engine project or updating an older Harness install.

`Harness/docs/template/changelog.md` tracks the reusable Harness_Unreal template itself. `Harness/Progress.md` is copied as a neutral project-facing dashboard and should only describe the target project's current status after installation.

## Copy Into A Project

Copy `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, and `Harness/` into the project root. Copy the root `README.md` only when the target does not already have one. `Harness/docs/template/changelog.md` is template provenance; keep project work history in task and cycle records instead of adding project entries there.

Review and merge these repository files instead of blindly replacing project-specific rules:

- `.gitattributes`: preserve the Unreal `*.uasset` and `*.umap` Git LFS rules unless the team has an explicit alternative.
- `.gitignore`: preserve project-specific ignore rules and add the Harness runtime exclusions.

Do not copy `.git/`, `.claude/`, `Harness/.runtime/`, `Harness/temp/`, Python caches, generated handoffs, or real project cycle logs from the template repository. The managed runtime is local and ignored, the release checker rejects a present `Harness/temp/` tree, and the packager excludes both local trees defensively.

Use `& Harness\harness.ps1 <command>` in Windows PowerShell or `sh Harness/harness.sh <command>` on POSIX for the stable command surface. The batch wrapper is a fixed-token convenience only: CMD reparses free-form metacharacters before a `.cmd` file can preserve them. Set `HARNESS_PYTHON` only when an explicit Python 3.10+ executable is required. Direct `python Harness/scripts/tools/*.py` calls remain supported for automation and diagnostics.

## Bootstrap Without System Python

When Python 3.10+ is not installed, run one explicit native-shell bootstrap:

```powershell
& Harness\harness.ps1 bootstrap
& Harness\harness.ps1 bootstrap --status
```

On Linux or macOS, use `sh Harness/harness.sh bootstrap`. Normal Harness commands never start a network download automatically, and the Windows launcher disables Python Install Manager automatic installation while probing existing commands. The bootstrap reuses a valid runtime without consulting uv or the network. Otherwise it accepts an explicitly supplied **uv 0.12.18** through `HARNESS_UV`, reuses the prior pinned runtime-local uv, or downloads the pinned uv 0.12.18 installer; it never implicitly trusts PATH uv. The downloaded installer is SHA-256 verified before execution, and uv installs the current patched Python 3.12 build. The runtime is isolated by OS/architecture under `Harness/.runtime/`, excluded from Git and release packages, and not registered globally.

For a closed network, set `HARNESS_UV` to an approved uv 0.12.18 executable and also provide the Python archive through a preseeded `UV_CACHE_DIR` / `HARNESS_UV_CACHE_DIR` or environment-based uv mirror such as `UV_PYTHON_DOWNLOADS_JSON_URL`. `UV_NO_CONFIG=1` deliberately ignores ambient uv configuration files, so mirror policy must be supplied through environment variables. The default online installer URL is not contacted when `HARNESS_UV` is explicitly set; a missing or wrong-version explicit uv fails closed. `HARNESS_RUNTIME_ROOT` can relocate a single platform's runtime, but it must not be a filesystem root, junction, or symlink and should point to an ignored local/cache location. If neither approved network access nor an offline Python source is available, use the documented manual-reading fallback; automated Harness commands cannot run without some Python runtime.

## Configure

1. Edit `Harness/config/project.json` and set `template_mode` to `false`.
2. Fill the project name, `.uproject`, engine version, engine root, and editor target.
3. Set `ci.mode` in `Harness/config/project.json` (`online_runner`, `closed_network_runner`, or `no_actions_or_runners`) per `Harness/docs/template/gitea-ci.md`; readiness `--strict` blocks connection while it is blank.
4. Register project docs in `Harness/config/docs.json`.
5. Fill `Harness/work/state.md` with the compact current snapshot and keep only the 3-5 highest-priority unresolved project items in `Harness/work/next.md`.
6. Fill `Harness/index/project_index.md` as a compact routing map.
7. Keep `Harness/Progress.md` as the short Korean dashboard for the target project. Replace the neutral `작성 필요:` bullets only after there is real project status to record.
8. Keep agent-facing Harness docs in English by default. Put Korean project status in `Harness/Progress.md`, and avoid long Korean logs that agents would repeatedly re-read.
9. Use `Harness/data/memory/*.jsonl` only when the project wants a reviewed memory layer. Private Gitea projects may commit reviewed daily shards; public template packages should keep real shards empty or absent. SQLite cache files under `Harness/data/` are local and ignored.
10. For parallel work, use separate worktrees and branches only when parallel isolation is needed. Create one `Harness/work/tasks/<task-id>.md` per task.
11. Review the read-only roles in `Harness/config/agents.json` and `Harness/agents/`. Keep the primary agent as integration owner; adapt provider-specific invocation outside the shared role contracts if needed.
12. Confirm Git LFS is installed and the `.gitattributes` rules match team policy before committing binary Unreal assets.
13. Read `Harness/docs/AgentFieldGuide.md` and remove or adapt any guidance that does not fit the project's workflow.

## Verify Setup

```powershell
& Harness\harness.ps1 context --request "initial setup"
& Harness\harness.ps1 init-plan
& Harness\harness.ps1 field-check
& Harness\harness.ps1 verify
```

Use the launcher's `field-check --branches <branch-a> <branch-b>` command only when the project intentionally maintains multiple branches that must be checked for remote alignment.

Run `& Harness\harness.ps1 readiness --strict` after filling project data. Do not treat the first connection as complete until strict readiness and `verify` pass. The aggregate verifier itself runs readiness without `--strict`, so routine work is blocked only by hard connection/config errors, while `--strict` also requires state, next, and project index to be free of template placeholders.

For CI setup, keep the template workflow as the Harness baseline and choose a runner mode from `Harness/docs/template/gitea-ci.md`. If the target Gitea server has no Actions or runners, run `& Harness\harness.ps1 local-gate` before commit or push instead of treating CI as passed. The local gate checks staged and unstaged changes separately and is read-only unless `--cleanup-caches` is supplied. For a real Unreal project, add the strongest practical project-specific tier from `Harness/docs/template/project-ci.md`; the reusable template CI does not replace an Editor build, commandlet, automation test, or PIE evidence. For the shortest agent checklist, use `Harness/docs/template/first-project-connect.md`.

## Update An Existing Harness Install

Run the migration audit from the new template checkout before replacing files:

```powershell
& C:\Path\To\NewHarnessTemplate\Harness\harness.ps1 migration-audit --target C:\Path\To\Project
& C:\Path\To\NewHarnessTemplate\Harness\harness.ps1 update --target C:\Path\To\Project
```

If neither checkout has Python 3.10+, bootstrap the new template launcher explicitly before this audit. The managed runtime stays inside that template checkout and the update tools can then inspect the target without requiring global Python.

An update is a reviewed migration, not a blind replacement. `Harness/template/manifest.json` is the ownership contract: preserve `project_owned`, review `managed_merge`, replace `template_owned` only when the installed baseline proves it is locally unchanged, and update generated receipts only after verification. Preserve project-specific config, docs, indexes, work records, Progress, and custom scripts.

Treat `project.json`, `docs.json`, `generated_artifacts.json`, `local_rules.md`, `record_policy.json`, `sensitive_allowlist.json`, `docs/project/`, indexes, work records, Progress, `scripts/project/`, and custom script behavior as project-owned. Review and merge root instructions, shared policy config, standard tools, and templates from the new Harness version. Use the template checkout's `Harness/docs/template/changelog.md` to understand what changed between template versions, but do not use it as a substitute for target-project task or cycle records. When adopting the compact-document rules, preserve removed history in existing task/cycle records or an archive before replacing current state, next, or Progress content.

For an active task whose final cycle records `stop_success` and concrete verification, use `& Harness\harness.ps1 close --task <task-id>` and add `--write` only after reviewing the preview. It updates task status and archives the task/cycle pair as one rollback-safe operation. The launcher's lower-level `archive` command remains available for records already marked completed and for old date-named cycles.

Recommended reviewed update flow:

1. Commit or back up the target project and run the new template launcher's `update` command. Keep the template and target as separate, non-nested directory trees so an update cannot write back into its own source inventory.
2. Add only absent template files with `--apply-missing`. This option requires an existing target `Harness/` directory and never overwrites an existing target file; use the normal initialization flow for a project without Harness.
3. Copy changed shared/standard template files into an empty comparison folder outside both the template and target trees with `--stage-review C:\Path\To\HarnessReview`. Existing review files are protected unless `--overwrite-stage` is explicitly supplied; a failed staging operation rolls back its changes.
4. Merge `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, shared config, and repository rules from the staged copy. Review standard tool replacements; keep project-specific behavior and unregistered custom tools.
5. Do not replace `project.json`, `docs.json`, project docs, `Harness/index/`, `Harness/work/`, or `Harness/Progress.md`. Migrate their structure only when needed. Review `Harness/docs/template/` separately as template-owned documentation and adopt changes only when they are useful provenance. Template scaffolding files inside those directories (`work/README.md`, `work/archive/README.md`, `work/tasks/README.md`, `task.example.md`, `docs/README.md`, `index/README.md`, examples) are staged as merge-review candidates so their guidance can follow the template version.
6. After the native bootstrap and launcher files are merged into the target, run `& C:\Path\To\Project\Harness\harness.ps1 bootstrap` there if the target has no Python 3.10+ and project policy permits the explicit install. A runtime bootstrapped in the separate template checkout is intentionally not copied into the target.
7. Search the retained material with `& C:\Path\To\Project\Harness\harness.ps1 knowledge --query "<current feature or issue>"` and refresh compact state/index files only from confirmed evidence.
8. Run the target launcher's `readiness --strict` and `verify`, accept the reviewed receipt as described below using the new template launcher, then run `& C:\Path\To\Project\Harness\harness.ps1 readiness --after-update --strict`. The after-update check requires the accepted receipt, so it comes last. Inspect `git diff --stat` and remove legacy split directories only after verification passes.
9. If the old project accumulated useful agent lessons, generalize them into `Harness/docs/AgentFieldGuide.md` or a project doc. Do not copy real paths, branch names, credentials, or active work logs into the reusable template.

When `Harness/config/template_receipt.json` is absent, the planner reports an unknown baseline and keeps conservative two-way `merge_review` / `replace_review` decisions. A valid receipt records raw upstream hashes and enables `safe_replace`, `keep_local`, and `merge_review` three-way classifications. Text files may also report `newline_only`, but raw hashes remain authoritative and no file is silently normalized. `--apply-missing` may add `safe_add` files; `safe_replace` remains a staged review candidate rather than an automatic overwrite.

After every template-owned or managed-merge action is resolved, rerun the plan. Then accept provenance in a separate invocation:

```powershell
& Harness\harness.ps1 update --target C:\Path\To\Project --accept-receipt
```

Receipt acceptance runs the target's standard verifier and refuses to write on failure or while review/apply actions remain. It records no timestamp as source identity and never invents an old baseline.

When a manual merge deliberately retains project additions, rerunning the planner will still show `merge_review`. To acknowledge that reviewed result, prepare a JSON object keyed by path, with `local_sha256` copied from the fresh plan's `local_hash`, `upstream_sha256` from `new_hash`, and a nonempty `reason`. Pass that file with `update --target <project> --accept-receipt --resolutions <review.json>`. Each entry is bound to both reviewed byte sequences; a changed file, unrecognized path, missing file, or failed verification prevents acceptance. The installed baseline remains the upstream hash, so a subsequent unchanged-upstream update correctly reports `keep_local`. Keep this project-specific review file outside the reusable template.

Version-specific upgrade notes:

- **Managed Python bootstrap**: merge `bootstrap.ps1`, `bootstrap.sh`, both launchers, the `.gitignore` runtime exclusion, and release/local-gate exclusions as one unit. The bootstrap is explicit and networked by default; closed networks should supply approved `uv` and Python mirrors instead of weakening checksum or TLS validation.
- **Read-only subagents**: `agents.json` version 3 registers `current-status` and `commit-explainer`, while `Harness/agents/` contains their provider-neutral contracts. `--apply-missing` can add absent prompt files, but merge-review `Harness/config/agents.json` so the Doctor sees the v3 delegation policy and both roles. Keep provider-specific adapters outside the shared contracts and preserve the primary agent as integration owner.
- **CI runner modes**: if the target project runs on private Gitea, review `Harness/docs/template/gitea-ci.md` before replacing workflows. A server with no Actions or no registered runners should use the launcher's `local-gate` command. Closed-network runners may need mirrored actions or a preseeded managed runtime instead of the public `actions/*` sources.
- **Project readiness gate**: the launcher's `verify` command includes `readiness` in standard (non-strict) mode, so only hard connection/config errors — blank required `project.json` fields, a missing or malformed `.uproject`, or an absent connection file — block routine completion. Lingering template placeholders in state, next, or project index are non-blocking warnings during routine work; run `readiness --strict` at the connection milestone to require them to be filled.
- **Project Unreal CI attachment**: keep template CI portable, then add target-project jobs from `Harness/docs/template/project-ci.md` after engine paths, maps, plugins, and automation are known.
- **Memory/data layer (`Harness/data/`)**: older installs have no `Harness/data/`. `--apply-missing` adds the scaffolding (`README.md`, `schema.sql`, `memory.example.jsonl`, empty `memory/`). Merge the new `.gitignore` entries **before the first commit** so local `Harness/data/*.sqlite*` caches are never committed; the `doctor` command warns when `Harness/data/` exists without those exclusions. The layer is optional — validate it with the launcher's `memory --doctor` command and leave the shards empty if the project does not want reviewed memory.
- **Archive modes**: older `harness_archive.py` handles only `--task`. The updated launcher `archive` command also archives old date-named cycle files (`2026-06-17.md`, `claude-2026-05-08.md`) with `--before YYYY-MM --archive`, and launcher `state-check` warns while completed tasks remain unarchived. After applying the tool review, run an `archive --before <this-month>` preview to drain accumulated date cycles into monthly archive folders.
- **Transitional doctor warnings**: between `--apply-missing` and finishing the staged review, newly added tool scripts are not yet registered in the old `tool_manifest.json`, so `harness_doctor.py` reports them as warnings. This is expected; it clears once the manifest review is applied. The plan output lists these cases under `Post-Apply Notes`.
- **Progress viewer**: `Harness/Progress_index.html` fetches `Progress.md` live, so open it through `Harness/Progress_view.cmd` or the launcher's `progress --serve` command; a plain `file://` open cannot fetch.
- **Ownership and receipt**: new templates ship `Harness/template/manifest.json`, project extension roots, and `template_receipt.example.json`. Receipt-free projects remain usable in conservative mode. Preserve `local_rules.md`, `sensitive_allowlist.json`, `docs/project/`, `scripts/project/`, and any existing receipt while staging the new ownership-aware tools.
- **Record policy and closeout**: `record_policy.json` is project-owned warning debt with stable IDs, mandatory reasons, and expiries. Keep its baseline empty unless a warning is intentionally time-bounded. The new `close` command validates the final cycle before changing status or archiving.
- **Generated artifact provenance**: `generated_artifacts.json` is project-owned and starts empty. Register only durable evidence, using a generator/revision, project-relative source/output paths, matching input/artifact revisions, a SHA-256, scope, acceptance, and verification command. Launcher `verify` validates it, and strict release checking treats pending or stale registered evidence as a blocker.

When migrating from the split worker layout:

- merge `Harness/Codex/config/` and `Harness/Claude/config/` into `Harness/config/`
- merge durable state and unresolved work into the single snapshots
- preserve worker-specific or conflicting history as separate files under `Harness/work/tasks/` and `Harness/work/cycles/`
- merge indexes and custom scripts deliberately
- move confirmed shared docs from `Harness/Common/docs/` into `Harness/docs/`
- remove split directories only after the single Harness passes verification

After updating:

```powershell
& Harness\harness.ps1 verify
```

Do not report the update complete until verification passes and `git diff --stat` shows only the intended migration.

## Close Out Real Project Work

Before committing or pushing a project that uses this template:

1. Run the smallest verification that proves the requested behavior.
2. Run `& Harness\harness.ps1 readiness --strict` after initialization or Harness updates (routine runs are covered non-strict inside `verify`).
3. Run `& Harness\harness.ps1 verify`.
4. Run the launcher's `field-check` command for root, field-guide, and Unreal Python wrapper hints.
5. Inspect `git diff --stat` and make sure generated assets/docs are intentionally included.
6. Keep `Harness/Progress.md` short; move detailed history into task/cycle records.
7. For requested multi-branch or multi-worktree syncs, verify local checkout status first, push the intended branches, then confirm remote refs with `git ls-remote --heads origin <branches...>`.

## Build A Clean Template Package

Run the strict release check only in the template repository. Real projects normally contain task and cycle records, which intentionally fail strict template-release hygiene.

```powershell
& Harness\harness.ps1 manifest --write
& Harness\harness.ps1 verify
& Harness\harness.ps1 release-check --strict
& Harness\harness.ps1 release-pack --write
```

Package write mode requires a current reviewed manifest, repeats the strict check, and blocks the ZIP when it fails. Manifest `hash_format` identifies canonical release bytes: CRLF becomes LF for known UTF-8 text types; binary and unknown types retain exact bytes. The ZIP uses the same bytes, fixed metadata, sorted uncompressed entries, and a temporary sibling file. This makes hashes and packages stable across Git checkout newline conversion without changing installation receipt raw hashes. It rejects outputs under `Harness/` or over source files and never follows template symlinks. Use `--force` only for exceptional non-manifest hygiene diagnostics; it does not bypass missing, stale, or invalid manifest data or output-path safety.
