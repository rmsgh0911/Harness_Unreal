# Harness Template Setup

Use this guide when copying the template into an Unreal Engine project or updating an older Harness install.

`Harness/docs/template/changelog.md` tracks the reusable Harness_Unreal template itself. `Harness/Progress.md` is copied as a neutral project-facing dashboard and should only describe the target project's current status after installation.

## Copy Into A Project

Copy `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, and `Harness/` into the project root. Copy the root `README.md` only when the target does not already have one. `Harness/docs/template/changelog.md` is template provenance; keep project work history in task and cycle records instead of adding project entries there.

Review and merge these repository files instead of blindly replacing project-specific rules:

- `.gitattributes`: preserve the Unreal `*.uasset` and `*.umap` Git LFS rules unless the team has an explicit alternative.
- `.gitignore`: preserve project-specific ignore rules and add the Harness runtime exclusions.

Do not copy `.git/`, `.claude/`, Python caches, generated handoffs, or real project cycle logs from the template repository.

## Configure

1. Edit `Harness/config/project.json` and set `template_mode` to `false`.
2. Fill the project name, `.uproject`, engine version, engine root, and editor target.
3. Register project docs in `Harness/config/docs.json`.
4. Fill `Harness/work/state.md` with the compact current snapshot and keep only the 3-5 highest-priority unresolved project items in `Harness/work/next.md`.
5. Fill `Harness/index/project_index.md` as a compact routing map.
6. Keep `Harness/Progress.md` as the short Korean dashboard for the target project. Replace the neutral `작성 필요:` bullets only after there is real project status to record.
7. Keep agent-facing Harness docs in English by default. Put Korean project status in `Harness/Progress.md`, and avoid long Korean logs that agents would repeatedly re-read.
8. Use `Harness/data/memory/*.jsonl` only when the project wants a reviewed memory layer. Private Gitea projects may commit reviewed daily shards; public template packages should keep real shards empty or absent. SQLite cache files under `Harness/data/` are local and ignored.
9. For parallel work, use separate worktrees and branches only when parallel isolation is needed. Create one `Harness/work/tasks/<task-id>.md` per task.
10. Confirm Git LFS is installed and the `.gitattributes` rules match team policy before committing binary Unreal assets.
11. Read `Harness/docs/AgentFieldGuide.md` and remove or adapt any guidance that does not fit the project's workflow.

## Verify Setup

```powershell
python Harness/scripts/tools/harness_context.py --request "initial setup"
python Harness/scripts/tools/harness_init_plan.py
python Harness/scripts/tools/harness_field_check.py
python Harness/scripts/tools/harness_verify_all.py
```

Use `harness_field_check.py --branches <branch-a> <branch-b>` only when the project intentionally maintains multiple branches that must be checked for remote alignment.

For CI setup, keep the template workflow as the Harness baseline and choose a runner mode from `Harness/docs/template/gitea-ci.md`. If the target Gitea server has no Actions or runners, use the documented local-only finish gate before commit or push instead of treating CI as passed. For a real Unreal project, add the strongest practical project-specific tier from `Harness/docs/template/project-ci.md`; the reusable template CI does not replace an Editor build, commandlet, automation test, or PIE evidence.

## Update An Existing Harness Install

Run the migration audit from the new template checkout before replacing files:

```powershell
python C:\Path\To\NewHarnessTemplate\Harness\scripts\tools\harness_migration_audit.py --target C:\Path\To\Project
python C:\Path\To\NewHarnessTemplate\Harness\scripts\tools\harness_update_plan.py --target C:\Path\To\Project
```

An update is a reviewed migration, not a blind replacement. Preserve project-specific config, docs, indexes, work records, Progress, and custom scripts.

Treat `project.json`, `docs.json`, project docs, indexes, work records, Progress, and custom script behavior as project-owned. Review and merge root instructions, shared policy config, standard tools, and templates from the new Harness version. Use the template checkout's `Harness/docs/template/changelog.md` to understand what changed between template versions, but do not use it as a substitute for target-project task or cycle records. When adopting the compact-document rules, preserve removed history in existing task/cycle records or an archive before replacing current state, next, or Progress content.

Completed task/cycle records can be preserved with `python Harness/scripts/tools/harness_archive.py --task <task-id> --archive`. Preview the command without `--archive` first.

Recommended reviewed update flow:

1. Commit or back up the target project and run `harness_update_plan.py` from the new template.
2. Add only absent template files with `--apply-missing`. This option requires an existing target `Harness/` directory and never overwrites an existing target file; use the normal initialization flow for a project without Harness.
3. Copy changed shared/standard template files into an empty comparison folder outside both the template and target trees with `--stage-review C:\Path\To\HarnessReview`. Existing review files are protected unless `--overwrite-stage` is explicitly supplied; a failed staging operation rolls back its changes.
4. Merge `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, shared config, and repository rules from the staged copy. Review standard tool replacements; keep project-specific behavior and unregistered custom tools.
5. Do not replace `project.json`, `docs.json`, project docs, `Harness/index/`, `Harness/work/`, or `Harness/Progress.md`. Migrate their structure only when needed. Review `Harness/docs/template/` separately as template-owned documentation and adopt changes only when they are useful provenance. Template scaffolding files inside those directories (`work/README.md`, `work/archive/README.md`, `work/tasks/README.md`, `task.example.md`, `docs/README.md`, `index/README.md`, examples) are staged as merge-review candidates so their guidance can follow the template version.
6. Search the retained material with `python Harness/scripts/tools/harness_knowledge.py --query "<current feature or issue>"` and refresh compact state/index files only from confirmed evidence.
7. Run `harness_verify_all.py`, inspect `git diff --stat`, and remove legacy split directories only after verification passes.
8. If the old project accumulated useful agent lessons, generalize them into `Harness/docs/AgentFieldGuide.md` or a project doc. Do not copy real paths, branch names, credentials, or active work logs into the reusable template.

Version-specific upgrade notes:

- **CI runner modes**: if the target project runs on private Gitea, review `Harness/docs/template/gitea-ci.md` before replacing workflows. A server with no Actions or no registered runners should use the local-only finish gate. Closed-network runners may need mirrored actions or preinstalled Python instead of the public `actions/*` sources.
- **Project Unreal CI attachment**: keep template CI portable, then add target-project jobs from `Harness/docs/template/project-ci.md` after engine paths, maps, plugins, and automation are known.
- **Memory/data layer (`Harness/data/`)**: older installs have no `Harness/data/`. `--apply-missing` adds the scaffolding (`README.md`, `schema.sql`, `memory.example.jsonl`, empty `memory/`). Merge the new `.gitignore` entries **before the first commit** so local `Harness/data/*.sqlite*` caches are never committed; `harness_doctor.py` warns when `Harness/data/` exists without those exclusions. The layer is optional — validate it with `python Harness/scripts/tools/harness_memory.py --doctor` and leave the shards empty if the project does not want reviewed memory.
- **Archive modes**: older `harness_archive.py` handles only `--task`. The updated tool also archives old date-named cycle files (`2026-06-17.md`, `claude-2026-05-08.md`) with `--before YYYY-MM --archive`, and `harness_state_check.py` warns while completed tasks remain unarchived. After applying the tool review, run a preview (`--before <this-month>`) to drain accumulated date cycles into monthly archive folders.
- **Transitional doctor warnings**: between `--apply-missing` and finishing the staged review, newly added tool scripts are not yet registered in the old `tool_manifest.json`, so `harness_doctor.py` reports them as warnings. This is expected; it clears once the manifest review is applied. The plan output lists these cases under `Post-Apply Notes`.
- **Progress viewer**: `Harness/Progress_index.html` fetches `Progress.md` live, so open it through `Harness/Progress_view.cmd` or `harness_progress_html.py --serve`; a plain `file://` open cannot fetch.

When migrating from the split worker layout:

- merge `Harness/Codex/config/` and `Harness/Claude/config/` into `Harness/config/`
- merge durable state and unresolved work into the single snapshots
- preserve worker-specific or conflicting history as separate files under `Harness/work/tasks/` and `Harness/work/cycles/`
- merge indexes and custom scripts deliberately
- move confirmed shared docs from `Harness/Common/docs/` into `Harness/docs/`
- remove split directories only after the single Harness passes verification

After updating:

```powershell
python Harness/scripts/tools/harness_verify_all.py
```

Do not report the update complete until verification passes and `git diff --stat` shows only the intended migration.

## Close Out Real Project Work

Before committing or pushing a project that uses this template:

1. Run the smallest verification that proves the requested behavior.
2. Run `python Harness/scripts/tools/harness_verify_all.py`.
3. Run `python Harness/scripts/tools/harness_field_check.py` for root, field-guide, and Unreal Python wrapper hints.
4. Inspect `git diff --stat` and make sure generated assets/docs are intentionally included.
5. Keep `Harness/Progress.md` short; move detailed history into task/cycle records.
6. For requested multi-branch or multi-worktree syncs, verify local checkout status first, push the intended branches, then confirm remote refs with `git ls-remote --heads origin <branches...>`.

## Build A Clean Template Package

Run the strict release check only in the template repository. Real projects normally contain task and cycle records, which intentionally fail strict template-release hygiene.

```powershell
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_release_check.py --strict
python Harness/scripts/tools/harness_release_pack.py --write
```

Package write mode repeats the strict check and blocks the ZIP when it fails. It writes through a temporary sibling file, rejects outputs under `Harness/` or over source files, and never follows template symlinks. Use `--force` only for exceptional hygiene diagnostics; it does not bypass output-path safety.
