# CLAUDE.md

This repository uses the Harness workflow.

## Mandatory Startup

Before starting any task:

1. Read the root `HARNESS.md`.
2. Read `Harness/work/state.md` and `Harness/work/next.md` before project work.
3. If Python is available, prefer:
   `python Harness/scripts/tools/harness_context.py --request "<user request>"`
4. Follow the default Harness loop:
   `implement -> minimal verification -> self-review -> record`.

For feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

Before the final response for project changes, check the smallest useful verification result, `git diff --stat`, and whether `Harness/docs/Progress.md` needs a brief Korean update.

## Defaults

- Do not broadly scan the whole repository.
- Read and edit only files directly relevant to the request.
- Use `Harness/index/project_index.md` as a routing hint when it exists; verify final assumptions against actual code, config, assets, logs, or build output.
- Prefer one primary worker.
- Do not use external reviewers, summary agents, or multi-agent mode unless the user explicitly asks.
- If unsure, do not skip Harness; run the startup context command above.

## Claude Code As Primary Worker

- Claude Code may work as the primary single worker without Codex.
- If the human explicitly switches the primary worker, follow the worker switching rules in `HARNESS.md`.
- When receiving work from another worker, first read `HARNESS.md`, `Harness/work/state.md`, `Harness/work/next.md`, today's `Harness/work/cycles/YYYY-MM-DD.md` if it exists, and the current `git status/diff`.

## Claude Code Notes

- Use planning mode only when the implementation scope is broad or risky. For small fixes with clear scope, proceed directly.
- Treat `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/work/cycles/` as the durable project context. Use Claude memory only as a supplement.
- When referencing files in the worktree, prefer paths relative to the repository root.

## Repository-Specific Additions

Append short repository-specific rules below this section only when needed.
