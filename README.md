# Unreal Harness Template

Codex, Claude Code, and other AI agents use the same `Harness/` operating layer in this Unreal Engine template.

Parallel work is isolated with Git worktrees and branches. Agent names, branch names, worktree paths, and timestamps belong in task-specific records under `Harness/work/tasks/`, not as repeated edits to shared `state.md` or `next.md`.

## Quick Start

```powershell
python Harness/scripts/tools/harness_context.py --request "<task>"
python Harness/scripts/tools/harness_verify_all.py
```

For parallel work:

1. Create a worktree and branch for the task.
2. Create `Harness/work/tasks/<task-id>.md` from `task.example.md`.
3. Record short cycles with:

```powershell
python Harness/scripts/tools/harness_cycle.py "Task Name" --task <task-id> --worker Codex
```

Read `HARNESS.md` for operating rules and `INSTALL.md` for installation or migration.
