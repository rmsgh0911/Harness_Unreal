# Harness Template Setup

Use this guide when copying the template into an Unreal Engine project or updating an older Harness install.

## Copy Into A Project

Copy `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, `INSTALL.md`, and `Harness/` into the project root. Copy the root `README.md` only when the target does not already have one.

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
6. Keep `Harness/Progress.md` as the short Korean dashboard.
7. For parallel work, use separate worktrees and branches. Create one `Harness/work/tasks/<task-id>.md` per task.
8. Confirm Git LFS is installed and the `.gitattributes` rules match team policy before committing binary Unreal assets.

## Verify Setup

```powershell
python Harness/scripts/tools/harness_context.py --request "initial setup"
python Harness/scripts/tools/harness_init_plan.py
python Harness/scripts/tools/harness_verify_all.py
```

## Update An Existing Harness Install

Run the migration audit from the new template checkout before replacing files:

```powershell
python C:\Path\To\NewHarnessTemplate\Harness\scripts\tools\harness_migration_audit.py --target C:\Path\To\Project
python C:\Path\To\NewHarnessTemplate\Harness\scripts\tools\harness_update_plan.py --target C:\Path\To\Project
```

An update is a reviewed migration, not a blind replacement. Preserve project-specific config, docs, indexes, work records, Progress, and custom scripts.

Treat `project.json`, `docs.json`, project docs, indexes, work records, Progress, and custom script behavior as project-owned. Review and merge root instructions, shared policy config, standard tools, and templates from the new Harness version. When adopting the compact-document rules, preserve removed history in existing task/cycle records or an archive before replacing current state, next, or Progress content.

Completed task/cycle records can be preserved with `python Harness/scripts/tools/harness_archive.py --task <task-id> --archive`. Preview the command without `--archive` first.

Recommended reviewed update flow:

1. Commit or back up the target project and run `harness_update_plan.py` from the new template.
2. Add only absent template files with `--apply-missing`. This option never overwrites an existing target file.
3. Copy changed shared/standard template files into a separate comparison folder with `--stage-review C:\Path\To\HarnessReview`.
4. Merge `AGENTS.md`, `CLAUDE.md`, `HARNESS.md`, shared config, and repository rules from the staged copy. Review standard tool replacements; keep project-specific behavior and unregistered custom tools.
5. Do not replace `project.json`, `docs.json`, `Harness/docs/`, `Harness/index/`, `Harness/work/`, or `Harness/Progress.md`. Migrate their structure only when needed.
6. Search the retained material with `python Harness/scripts/tools/harness_knowledge.py --query "<current feature or issue>"` and refresh compact state/index files only from confirmed evidence.
7. Run `harness_verify_all.py`, inspect `git diff --stat`, and remove legacy split directories only after verification passes.

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

## Build A Clean Template Package

Run the strict release check only in the template repository. Real projects normally contain task and cycle records, which intentionally fail strict template-release hygiene.

```powershell
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_release_check.py --strict
python Harness/scripts/tools/harness_release_pack.py --write
```
