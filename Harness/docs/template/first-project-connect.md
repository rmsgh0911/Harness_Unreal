# First Project Connect

Use this checklist when an agent copies Harness into a real Unreal project for the first time, or after a Harness update that changes setup, tooling, or verification behavior.

## Agent Flow

```powershell
python Harness/scripts/tools/harness_context.py --request "connect Harness to this project"
python Harness/scripts/tools/harness_project_fill.py --json
python Harness/scripts/tools/harness_project_fill.py --write
python Harness/scripts/tools/harness_project_readiness.py
python Harness/scripts/tools/harness_verify_all.py
```

If the target Gitea project has no Actions or registered runners, finish with:

```powershell
python Harness/scripts/tools/harness_local_gate.py
```

## Connection Is Not Complete Until

- `Harness/config/project.json` has `template_mode: false`.
- `project_name`, `uproject_file`, `engine_version`, `build.engine_root`, and `build.editor_target_name` are filled.
- The configured `.uproject` file exists.
- `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` no longer contain template placeholders.
- `Harness/index/verification_map.md` records the practical Unreal verification tier for the project.
- The agent records any Unreal build, commandlet, PIE, or manual verification that cannot run on the current machine.

## After Updating An Existing Project

```powershell
python C:\Path\To\NewHarnessTemplate\Harness\scripts\tools\harness_update_plan.py --target C:\Path\To\Project
python Harness/scripts/tools/harness_project_readiness.py --after-update
python Harness/scripts/tools/harness_verify_all.py
```

Use `harness_update_plan.py --stage-review` for changed shared files, then re-run readiness after the staged review is merged.
