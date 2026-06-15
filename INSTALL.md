# Harness Template Setup

Use this guide when copying this template into a real Unreal Engine project or updating an older Harness install.

This template contains two independent worker areas:

- `Harness/Codex/` for Codex
- `Harness/Claude/` for Claude Code

Shared confirmed project documents and stable policies live under `Harness/Common/`.

## Copy Into A Project

Copy these items into the Unreal project root:

- `README.md` when the target project does not already have one
- `AGENTS.md`
- `CLAUDE.md`
- `HARNESS.md`
- `Harness/`

Do not copy local repository or machine-specific files:

- `.git/`
- `.claude/`
- `__pycache__/`
- `.pytest_cache/`
- real `Harness/Codex/work/cycles/*.md` files
- real `Harness/Claude/work/cycles/*.md` files
- generated handoff files

Keep both worker cycle directories and their `.gitkeep` files.

## Configure Shared Material

1. Put confirmed shared project documents under `Harness/Common/docs/`.
2. Keep `Harness/Common/policies/` limited to stable policies approved for both workers.
3. Do not place active worker state, indexes, configs, scripts, cycle logs, or Progress dashboards under `Harness/Common/`.

## Configure Codex

1. Edit `Harness/Codex/config/project.json`.
2. Set `template_mode` to `false`.
3. Fill at least:
   - `project_name`
   - `uproject_file`
   - `engine_version`
   - `build.engine_root`
   - `build.editor_target_name`
4. Fill `Harness/Codex/work/state.md` with current confirmed project facts.
5. Fill `Harness/Codex/work/next.md` with only unresolved Codex work and decisions.
6. Fill `Harness/Codex/index/project_index.md` as a compact Codex routing map.
7. Fill `Harness/Codex/index/api_surface.md` and `verification_map.md` when relevant.
8. Keep `Harness/Codex/Progress.md` as the short Korean Codex dashboard.

## Configure Claude Code

1. Edit `Harness/Claude/config/project.json`.
2. Set `template_mode` to `false`.
3. Fill at least:
   - `project_name`
   - `uproject_file`
   - `engine_version`
   - `build.engine_root`
   - `build.editor_target_name`
4. Fill `Harness/Claude/work/state.md` with current confirmed project facts.
5. Fill `Harness/Claude/work/next.md` with only unresolved Claude Code work and decisions.
6. Fill `Harness/Claude/index/project_index.md` as a compact Claude Code routing map.
7. Fill `Harness/Claude/index/api_surface.md` and `verification_map.md` when relevant.
8. Keep `Harness/Claude/Progress.md` as the short Korean Claude Code dashboard.

Worker indexes and work records may differ because they represent each worker's branch and confirmed context. Verify final assumptions against actual code, config, assets, logs, or build output.

## Verify Setup

Run both worker checks from the project root:

```powershell
python Harness/Codex/scripts/tools/harness_context.py --request "initial setup"
python Harness/Codex/scripts/tools/harness_init_plan.py
python Harness/Codex/scripts/tools/harness_verify_all.py

python Harness/Claude/scripts/tools/harness_context.py --request "initial setup"
python Harness/Claude/scripts/tools/harness_init_plan.py
python Harness/Claude/scripts/tools/harness_verify_all.py
```

For Unreal build verification, configure each worker's `project.json`, then run the relevant worker command:

```powershell
Harness/Codex/scripts/build/build_verify.cmd -Mode Editor
Harness/Claude/scripts/build/build_verify.cmd -Mode Editor
```

## Update An Existing Harness Install

Audit the target with both worker tools before replacing files:

```powershell
python Harness/Codex/scripts/tools/harness_migration_audit.py --target C:\Path\To\Project
python Harness/Claude/scripts/tools/harness_migration_audit.py --target C:\Path\To\Project
```

An update is a reviewed migration, not a blind replacement of the target `Harness/` folder.

When migrating the legacy single-worker layout:

- copy or merge legacy `Harness/config/project.json` and `docs.json` into both worker config areas
- copy or merge legacy `Harness/work/`, `Harness/index/`, and `Progress.md` into both worker areas as an initial snapshot
- move confirmed project documents from legacy `Harness/docs/` or `Harness/doc/` into `Harness/Common/docs/`
- preserve custom scripts until their behavior has been merged into the relevant worker scripts
- remove legacy single-worker paths only after both worker areas pass verification

Preserve project-specific files unless the migration audit says otherwise:

- `Harness/Common/docs/`
- `Harness/Common/policies/` additions
- `Harness/Codex/config/project.json`
- `Harness/Codex/config/docs.json`
- `Harness/Codex/index/`
- `Harness/Codex/Progress.md`
- `Harness/Codex/work/`
- project-specific Codex script changes
- `Harness/Claude/config/project.json`
- `Harness/Claude/config/docs.json`
- `Harness/Claude/index/`
- `Harness/Claude/Progress.md`
- `Harness/Claude/work/`
- project-specific Claude Code script changes

Usually update or merge these template-controlled files:

- `AGENTS.md`
- `CLAUDE.md`
- `HARNESS.md`
- `Harness/README.md`
- worker `config/cycle_policy.json` and `config/agents.json`
- worker standard scripts and tools
- shared template documentation and policies

After updating, run both workers' `harness_verify_all.py`.

Do not report the update complete until both worker areas pass verification and `git diff --stat` shows only the intended migration.

## Build A Clean Template Package

From the template repository, run:

```powershell
python Harness/Codex/scripts/tools/harness_verify_all.py
python Harness/Claude/scripts/tools/harness_verify_all.py
python Harness/Codex/scripts/tools/harness_release_check.py --strict
python Harness/Codex/scripts/tools/harness_release_pack.py --json
python Harness/Codex/scripts/tools/harness_release_pack.py --write
```

The release check and package tools inspect the complete template, including both worker areas.
