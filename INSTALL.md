# Harness Template Setup

Use this guide when copying this template into a real Unreal Engine project or when updating an older Harness install.

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
- `Harness/work/cycles/*.md`
- `Harness/handoff.md`

Keep `Harness/work/cycles/.gitkeep` so the cycle directory exists after copy.

## Configure After Copy

1. Edit `Harness/config/project.json`.
2. Set `template_mode` to `false`.
3. Fill at least:
   - `project_name`
   - `uproject_file`
   - `engine_version`
   - `build.engine_root`
   - `build.editor_target_name`
4. Fill `Harness/work/state.md` with current confirmed project facts.
5. Fill `Harness/work/next.md` with only unresolved work and decisions.
6. Fill `Harness/index/project_index.md` as a compact project map.
7. Fill `Harness/index/api_surface.md` with Blueprint, MQTT, REST, JSON, and other compatibility-sensitive names.
8. Fill `Harness/index/verification_map.md` with project-specific minimum checks.

`Harness/index/` should be a short routing map, not a full project encyclopedia. Agents should still verify final assumptions against actual code, config, assets, logs, or build output.

## Verify Setup

Run these commands from the project root:

```powershell
python Harness/scripts/tools/harness_python_check.py
python Harness/scripts/tools/harness_context.py --request "initial setup"
python Harness/scripts/tools/harness_init_plan.py
python Harness/scripts/tools/harness_doctor.py
python Harness/scripts/tools/harness_verify_all.py
```

For Unreal build verification, configure `Harness/config/project.json` first, then use:

```powershell
Harness/scripts/build/build_verify.cmd -Mode Editor
```

## Update An Existing Harness Install

Before replacing files in an existing project, run:

```powershell
python Harness/scripts/tools/harness_migration_audit.py --target C:\Path\To\Project
```

Preserve project-specific files unless the migration audit says otherwise:

- `Harness/config/project.json`
- `Harness/config/docs.json`
- `Harness/docs/`
- `Harness/index/`
- `Harness/work/state.md`
- `Harness/work/next.md`
- `Harness/work/cycles/`

Usually update shared template files from the new version:

- `AGENTS.md`
- `CLAUDE.md`
- `HARNESS.md`
- `Harness/README.md`
- `Harness/scripts/`
- `Harness/config/cycle_policy.json`
- `Harness/config/agents.json`

After updating, run:

```powershell
python Harness/scripts/tools/harness_context.py --request "post-migration check"
python Harness/scripts/tools/harness_verify_all.py
```

## Build A Clean Template Package

From the template repository, run:

```powershell
python Harness/scripts/tools/harness_release_check.py --strict
python Harness/scripts/tools/harness_release_pack.py --json
python Harness/scripts/tools/harness_release_pack.py --write
```

The release package excludes local repo files, machine settings, Python caches, generated handoff files, and real cycle logs.
