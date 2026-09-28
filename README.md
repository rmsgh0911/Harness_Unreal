# Unreal Harness Template

Codex, Claude Code, and other AI agents use the same `Harness/` operating layer in this Unreal Engine template. The default shape is one checkout; parallel Git worktrees are optional and used only when a project needs isolated concurrent work.

Parallel work, when a project needs it, is isolated with Git worktrees and branches. Projects that do not run parallel tasks can use one normal checkout. Agent names, branch names, worktree paths, and timestamps belong in task-specific records under `Harness/work/tasks/`, not as repeated edits to shared `state.md` or `next.md`.

## Quick Start

If Python 3.10+ is already available, run the normal commands directly:

```powershell
& Harness\harness.ps1 context --request "<task>"
& Harness\harness.ps1 readiness --strict
& Harness\harness.ps1 verify
```

If Python is not installed, explicitly create an isolated project-local runtime first:

```powershell
& Harness\harness.ps1 bootstrap
& Harness\harness.ps1 bootstrap --status
```

On Linux or macOS, use `sh Harness/harness.sh bootstrap` and then the same normal subcommands. Bootstrap is never implicit: the explicit command downloads a pinned, checksum-verified `uv` installer when needed, and `uv` installs managed Python 3.12 under ignored `Harness/.runtime/` without modifying PATH, shell profiles, or the Windows Python registry. Every registered standard tool has a launcher alias, so use the launcher after bootstrap rather than expecting a new global `python` command. For offline or mirrored environments, provide the pinned `uv` 0.12.18 executable through `HARNESS_UV`, and provide the Python archive through an environment-configured uv mirror or a preseeded `UV_CACHE_DIR` / `HARNESS_UV_CACHE_DIR`. `HARNESS_PYTHON` still takes precedence when an explicit Python 3.10+ executable is available, and direct `python Harness/scripts/tools/*.py` calls remain supported when automation already supplies an interpreter.

Use the PowerShell launcher for Windows requests or paths containing free-form text. `harness.cmd` remains a fixed-token convenience entry point, but CMD reparses metacharacters such as `&` and `%...%` before a batch file can preserve them.

Use `--strict` readiness only at the connection milestone (first install or Harness update); the routine launcher `verify` command already runs the non-strict readiness check.

If the target Gitea repository has no Actions or registered runners, use the local gate before commit or push:

```powershell
& Harness\harness.ps1 local-gate
```

Optional local memory uses daily JSONL shards and a rebuildable SQLite cache:

```powershell
& Harness\harness.ps1 memory --query "<topic>" --limit 5
& Harness\harness.ps1 memory --doctor
```

For optional parallel work:

1. Create a worktree and branch for the task only when parallel isolation is needed.
2. Create `Harness/work/tasks/<task-id>.md` from `task.example.md`.
3. Record short cycles with:

```powershell
& Harness\harness.ps1 cycle "Task Name" --task <task-id> --worker Codex
```

Read `HARNESS.md` for operating rules and `Harness/docs/template/setup.md` for installation or migration. For CI rollout, no-runner Gitea use, or closed-network runners, also review `Harness/docs/template/gitea-ci.md` and `Harness/docs/template/project-ci.md`.

## What This Template Optimizes For

- Narrow startup context instead of broad repository scans.
- Evidence-backed Unreal changes: build output, commandlet status, generated JSON, screenshots, or manual PIE notes depending on the risk.
- Compact current-state files and detailed task/cycle records, so agents do not bury important facts in long dashboards.
- Optional parallel branch/worktree delivery with explicit final remote-ref checks when branch sync is requested.
- Reviewed Harness migrations that preserve project-owned docs, config, indexes, work records, Progress, and custom tools.
- Continuous verification on every push via `.github/workflows/tests.yml` when CI exists, or the launcher `local-gate` command as the local finish gate when private Gitea has no Actions or runners.
- A separate project-CI attachment path for real Unreal builds, commandlets, and PIE evidence.

For practical lessons learned from real project use, read `Harness/docs/AgentFieldGuide.md`.
