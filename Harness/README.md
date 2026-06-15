# Harness Folder

All supported agents use this single Harness layout. Parallel work is isolated by Git worktrees and branches, not by agent-specific Harness directories.

## Layout

- `config/`: project, docs, cycle, and agent configuration
- `docs/`: confirmed project documents
- `index/`: compact project routing maps
- `scripts/`: build, Unreal, and Harness tools
- `work/state.md`: latest confirmed project facts
- `work/next.md`: unresolved project-level work and decisions
- `work/tasks/`: one conflict-resistant record per active task or branch
- `work/cycles/`: short task-scoped work loop records
- `Progress.md`: short Korean human-facing dashboard

## Standard Commands

```powershell
python Harness/scripts/tools/harness_context.py --request "<task description>"
python Harness/scripts/tools/harness_context.py --request "<task description>" --task <task-id>
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_cycle.py "Task Name" --task <task-id> --worker <agent>
```

For parallel work, create a separate worktree and branch, then create `Harness/work/tasks/<task-id>.md`. Keep agent names and timestamps there rather than repeatedly editing shared `state.md` or `next.md`.
