# First Project Connect

Use this checklist when an agent copies Harness into a real Unreal project for the first time, or after a Harness update that changes setup, tooling, or verification behavior.

## Agent Flow

If Python 3.10+ is unavailable, run the target's explicit native bootstrap before the first `context` command, only when project policy permits the install:

```powershell
& Harness\harness.ps1 bootstrap
```

```powershell
& Harness\harness.ps1 context --request "connect Harness to this project"
& Harness\harness.ps1 project-fill --json
& Harness\harness.ps1 project-fill --write
& Harness\harness.ps1 readiness --strict
& Harness\harness.ps1 verify
```

Use `--strict` at this connection milestone so lingering template placeholders in state, next, and project index also block completion. Routine launcher `verify` runs readiness without `--strict`, so only hard connection/config errors (blank required fields, a missing or malformed `.uproject`) block everyday work.

If the target Gitea project has no Actions or registered runners, finish with:

```powershell
& Harness\harness.ps1 local-gate
```

## Connection Is Not Complete Until

- `Harness/config/project.json` has `template_mode: false`.
- `project_name`, `uproject_file`, `engine_version`, `build.engine_root`, and `build.editor_target_name` are filled.
- `ci.mode` declares the finish-gate policy (`online_runner`, `closed_network_runner`, or `no_actions_or_runners`) per `Harness/docs/template/gitea-ci.md`.
- The configured `.uproject` file exists.
- `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` no longer contain template placeholders.
- `Harness/index/verification_map.md` records the practical Unreal verification tier for the project.
- The agent records any Unreal build, commandlet, PIE, or manual verification that cannot run on the current machine.

## After Updating An Existing Project

If the new template checkout has no usable Python 3.10+ runtime, bootstrap that checkout before invoking its update tool:

```powershell
& C:\Path\To\NewHarnessTemplate\Harness\harness.ps1 bootstrap
```

```powershell
& C:\Path\To\NewHarnessTemplate\Harness\harness.ps1 update --target C:\Path\To\Project
```

Use the new template launcher's `update --stage-review <dir>` command for changed shared files, then merge the reviewed native bootstrap/launcher files before invoking the target launcher. If the target has no Python 3.10+, run the following after that merge, only when project policy permits the explicit install; the separate template checkout's managed runtime is not copied:

```powershell
& C:\Path\To\Project\Harness\harness.ps1 bootstrap
```

Then finish through the target launcher:

```powershell
& C:\Path\To\Project\Harness\harness.ps1 readiness --after-update --strict
& C:\Path\To\Project\Harness\harness.ps1 verify
```
