# Unreal Harness Template

Codex, Claude Code, and other AI agents use the same `Harness/` operating layer in this Unreal Engine template. The default shape is one checkout; parallel Git worktrees are optional and used only when a project needs isolated concurrent work.

Parallel work, when a project needs it, is isolated with Git worktrees and branches. Projects that do not run parallel tasks can use one normal checkout. Agent names, branch names, worktree paths, and timestamps belong in task-specific records under `Harness/work/tasks/`, not as repeated edits to shared `state.md` or `next.md`.

## Quick Start

```powershell
python Harness/scripts/tools/harness_context.py --request "<task>"
python Harness/scripts/tools/harness_verify_all.py
```

Optional local memory uses daily JSONL shards and a rebuildable SQLite cache:

```powershell
python Harness/scripts/tools/harness_memory.py --query "<topic>" --limit 5
python Harness/scripts/tools/harness_memory.py --doctor
```

For optional parallel work:

1. Create a worktree and branch for the task only when parallel isolation is needed.
2. Create `Harness/work/tasks/<task-id>.md` from `task.example.md`.
3. Record short cycles with:

```powershell
python Harness/scripts/tools/harness_cycle.py "Task Name" --task <task-id> --worker Codex
```

Read `HARNESS.md` for operating rules and `Harness/docs/template/setup.md` for installation or migration.

## What This Template Optimizes For

- Narrow startup context instead of broad repository scans.
- Evidence-backed Unreal changes: build output, commandlet status, generated JSON, screenshots, or manual PIE notes depending on the risk.
- Compact current-state files and detailed task/cycle records, so agents do not bury important facts in long dashboards.
- Optional parallel branch/worktree delivery with explicit final remote-ref checks when branch sync is requested.
- Reviewed Harness migrations that preserve project-owned docs, config, indexes, work records, Progress, and custom tools.

For practical lessons learned from real project use, read `Harness/docs/AgentFieldGuide.md`.
