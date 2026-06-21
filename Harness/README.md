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

Keep the current decision surface compact:

- `Progress.md`: four sections, about 40 lines total, and at most three core bullets per section
- `work/state.md`: Project, Current State, Latest Verification, and Risks; normally no more than 80 lines
- `work/next.md`: only the 3-5 highest-priority unresolved project items
- detailed history: task/cycle records or an optional project backlog document, never the current dashboard

## Standard Commands

```powershell
python Harness/scripts/tools/harness_context.py --request "<task description>"
python Harness/scripts/tools/harness_context.py --request "<task description>" --task <task-id>
python Harness/scripts/tools/harness_context.py --request "<task description>" --all-next
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_cycle.py "Task Name" --task <task-id> --worker <agent>
python Harness/scripts/tools/harness_iteration_status.py --request "<repeated task>" --task <task-id>
python Harness/scripts/tools/harness_update_plan.py --target C:\Path\To\OlderProject
python Harness/scripts/tools/harness_knowledge.py --query "<feature or issue>"
```

Use the context briefing first, then open only the recommended sections or files. Read the full state, next, and index files only when Python is unavailable, the briefing reports a conflict, or the request needs broader project context.

For parallel work, create a separate worktree and branch, then create `Harness/work/tasks/<task-id>.md`. Keep agent names and timestamps there rather than repeatedly editing shared `state.md` or `next.md`.
