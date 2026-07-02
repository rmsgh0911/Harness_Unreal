# Harness Folder

This Harness layout works for both a single normal checkout and optional parallel Git worktrees.

All supported agents use this single Harness layout. If a project uses parallel agents or parallel tasks, isolate that work with Git worktrees and branches instead of agent-specific Harness directories. A simple project can use one normal checkout.

## Layout

- `config/`: project, docs, cycle, and agent configuration
- `data/`: optional daily JSONL memory shards, examples, schema, and ignored local SQLite cache
- `docs/`: confirmed project documents
- `index/`: compact project routing maps
- `scripts/`: build, Unreal, and Harness tools
- `work/state.md`: latest confirmed project facts
- `work/next.md`: unresolved project-level work and decisions
- `work/tasks/`: one conflict-resistant record per active task or branch
- `work/cycles/`: short task-scoped work loop records
- `Progress.md`: short Korean human-facing dashboard
- `Progress_index.html`: tracked convenience viewer that loads `Progress.md` at view time
- `Progress_view.cmd`: double-click launcher that serves `Harness/` on localhost so the viewer can fetch the live `Progress.md`

Keep the current decision surface compact:

- `Progress.md`: four sections, about 40 lines total, and at most three core bullets per section
- `work/state.md`: Project, Current State, Latest Verification, and Risks; normally no more than 80 lines
- `work/next.md`: only the 3-5 highest-priority unresolved project items
- detailed history: task/cycle records or an optional project backlog document, never the current dashboard

## Primary Command Surface

Most daily work should fit through this small command surface:

```powershell
python Harness/scripts/tools/harness_context.py --request "<task description>"
python Harness/scripts/tools/harness_cycle.py "Task Name" --task <task-id> --worker <agent>
python Harness/scripts/tools/harness_project_readiness.py
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_local_gate.py
python Harness/scripts/tools/harness_handoff.py --request "<handoff summary>"
python Harness/scripts/tools/harness_update_plan.py --target C:\Path\To\OlderProject
```

Use the rest of the tools as focused diagnostics, migration helpers, or optional project features.

Use `harness_local_gate.py` instead of server CI when a private Gitea project has no Actions or registered runners. It runs the local test/verify/cache-cleanup finish gate, checks diff hygiene, and prints `git diff --stat`.

Use `harness_project_readiness.py --strict` at the connection milestone (after first install or Harness update). Inside routine `harness_verify_all.py` it runs non-strict: hard connection/config errors block, while lingering template placeholders are non-blocking warnings until you run it with `--strict`.

## Supporting Commands

```powershell
python Harness/scripts/tools/harness_context.py --request "<task description>" --task <task-id>
python Harness/scripts/tools/harness_context.py --request "<task description>" --all-next
python Harness/scripts/tools/harness_iteration_status.py --request "<repeated task>" --task <task-id>
python Harness/scripts/tools/harness_knowledge.py --query "<feature or issue>"
python Harness/scripts/tools/harness_memory.py --query "<feature or issue>" --limit 5
python Harness/scripts/tools/harness_progress_html.py --write
python Harness/scripts/tools/harness_progress_html.py --serve
```

Use the context briefing first, then open only the recommended sections or files. Read the full state, next, and index files only when Python is unavailable, the briefing reports a conflict, or the request needs broader project context.

Use `harness_memory.py` only for compact routing hints that still need confirmation against source, config, assets, logs, docs, or verification output. `Progress_index.html` is a stable viewer; routine status changes should update `Progress.md` and then reload the viewer. Because browsers block local `fetch()` over `file://`, open the viewer live with `Progress_view.cmd` or `python Harness/scripts/tools/harness_progress_html.py --serve`.

For parallel work, create a separate worktree and branch only when the task actually needs parallel isolation, then create `Harness/work/tasks/<task-id>.md`. Keep agent names and timestamps there rather than repeatedly editing shared `state.md` or `next.md`.

## Field Guide

Read `Harness/docs/AgentFieldGuide.md` when starting a new project, onboarding a new agent, debugging a repeated failure, or coordinating optional parallel worktrees. It captures the practical checks that prevent common Unreal Harness mistakes: wrong project root, unverified handoff claims, non-idempotent generated data, UI checks that miss runtime binding, and branch syncs that stop before remote refs are aligned.
