# CLAUDE.md

This repository uses the Harness workflow.

## Mandatory Startup

Before starting any task:

1. Read the root `HARNESS.md`.
2. Read `Harness/README.md` for the single Harness and worktree layout.
3. Before editing any project file, run this command unless Python is unavailable:
   `python Harness/scripts/tools/harness_context.py --request "<user request>"`
   Add `--task <task-id>` when working from a parallel task record.
4. Read only the state, next, task, cycle, or index sections recommended by the context briefing.
5. Follow the default Harness loop:
   `implement -> minimal verification -> self-review -> record`.

If the context command cannot run, manually read `HARNESS.md`, `Harness/README.md`, `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` when present before editing.

For feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

Before the final response for project changes, check the smallest useful verification result, `git diff --stat`, and whether `Harness/Progress.md` needs a brief Korean update.

## Defaults

- Do not broadly scan the whole repository.
- Read and edit only files directly relevant to the request.
- Use `Harness/index/project_index.md` as a routing hint when it exists; verify final assumptions against actual code, config, assets, logs, or build output.
- Prefer one primary worker.
- Do not use external reviewers, summary agents, or multi-agent mode unless the user explicitly asks.
- If unsure, do not skip Harness; run the startup context command above or apply the manual fallback reads.

Keep repository-specific additions short and append them below this section only when needed.
