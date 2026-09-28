# Verification Map

Task-type-specific minimum verification guidance. Keep entries short and practical.

## Minimum Required Tier (fill per project)

Pin the mandatory verification tier for each change type after connecting the project (tiers are defined in `Harness/docs/template/project-ci.md`). Example:

- C++ / module change: TODO (e.g., Tier 1 editor build required)
- Config change: TODO (e.g., Tier 0 tool checks + affected runtime path)
- UI / UMG / input change: TODO (e.g., Tier 3 PIE note required)
- Content / asset change: TODO (e.g., manual editor check recorded)
- CI workflow change: TODO (e.g., Ubuntu + Windows workflow green, or launcher `local-gate` evidence when no runners)

## C++ Source Change

Minimum:

- Compile the relevant target when practical.
- Check include and module dependency impact.

## Config Change

Minimum:

- Inspect the changed config key and the runtime path that consumes it.
- Run the smallest relevant project or Harness verification command.

## CI Workflow Change

Minimum:

- Run `& Harness\harness.ps1 verify` (or `sh Harness/harness.sh verify` on POSIX).
- Inspect `__pycache__/` and `*.pyc` before strict template verification; remove them explicitly with the launcher's `local-gate --cleanup-caches` command when needed.
- Use `verify --skip-tool-tests` only after a separate test step has already run.
- For Windows workflow changes, parse `Harness/scripts/build/build_verify.ps1` with the PowerShell parser.
- For Gitea runner assumptions, check `Harness/docs/template/gitea-ci.md`.
- If Actions or runners are unavailable, run the launcher's `local-gate` command and record the missing CI limitation.

## Unreal Project CI Attachment

Minimum:

- Keep template-level CI green first with the launcher `verify` command.
- In real projects, fill `Harness/config/project.json`, set `template_mode` to `false`, and add a target-project CI job for the strongest practical tier in `Harness/docs/template/project-ci.md`.
- Prefer a Windows runner for Editor builds, PowerShell scripts, Windows path handling, and Unreal automation.
- If CI cannot run Unreal, record the local build, commandlet, PIE, or manual evidence requirement in the task or cycle record.

## Blueprint-Facing Change

Minimum:

- Confirm no unintended UFUNCTION or UPROPERTY rename/signature change.
- Record manual PIE verification needs when automation cannot prove behavior.

## Asset, Map, UI, Camera, Or Input Change

Minimum:

- Record the required manual PIE or editor verification.
- Avoid broad asset moves, redirector cleanup, or renames unless explicitly requested.
