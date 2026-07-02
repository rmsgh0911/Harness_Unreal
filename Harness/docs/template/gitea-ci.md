# Gitea CI Modes

Use this note when the template is copied into a private Gitea project. The checked-in workflow is intentionally GitHub Actions compatible because Gitea Actions reads `.github/workflows/` by default.

## Online-Compatible Runner

Use `.github/workflows/tests.yml` unchanged when the runner can reach GitHub action sources.

Requirements:

- Actions are enabled for the Gitea repository.
- A Gitea `act_runner` is registered for Linux, and optionally Windows.
- The runner can download `actions/checkout` and `actions/setup-python`.
- Python 3.12 is available through `actions/setup-python`.

This mode proves the reusable Harness package with tool tests, cache cleanup, and `harness_verify_all.py`.

## No Actions Or Runners

If the Gitea server has no Actions support, no enabled Actions setting, or no registered runners, leave `.github/workflows/tests.yml` in the repository as dormant template metadata and use the local finish gate instead.

Local-only minimum before commit or push:

```powershell
python Harness/scripts/tools/harness_local_gate.py
```

For template releases, add:

```powershell
python Harness/scripts/tools/harness_local_gate.py --release
python Harness/scripts/tools/harness_release_pack.py --write
```

This mode is safe because Harness tools are read-only by default, write modes require explicit options, and `harness_update_plan.py --apply-missing` never overwrites existing project files. The missing safety net is automatic server-side enforcement: record any skipped Unreal build, commandlet, PIE, or Windows-runner check in the task or cycle record before treating the work as release-ready.

## Closed-Network Runner

For an offline or restricted company network, pick one of these supported patterns before enabling the workflow broadly:

- Mirror `actions/checkout` and `actions/setup-python` into the internal action registry, then rewrite the workflow `uses:` lines to the mirrored locations.
- Preinstall Python 3.12 on the runner image and replace `actions/setup-python` with a direct `python --version` check.
- Keep the cache cleanup and `python Harness/scripts/tools/harness_verify_all.py --skip-tool-tests` step even when the setup steps change.

Do not silently drop the Windows job if the project relies on PowerShell build scripts, Windows path behavior, or Unreal Editor automation. If the company CI cannot provide Windows runners, record that limitation in `Harness/index/verification_map.md` and require local Windows verification before release branches.

## Recommended Gitea Policy

- Declare the chosen mode in `Harness/config/project.json` under `ci.mode` (`online_runner`, `closed_network_runner`, or `no_actions_or_runners`); `harness_project_readiness.py` warns while it is blank so the finish gate stays explicit.
- Treat the workflow in this template as the public baseline.
- If Actions are unavailable, explicitly use the local-only finish gate above instead of treating CI as implicitly passed.
- Keep project-specific CI changes in the target project, not in the reusable template, unless they are useful to every Unreal Harness install.
- When a target project uses mirrored actions or a preinstalled Python image, document the runner assumption near the project workflow so future Harness updates do not replace it accidentally.
