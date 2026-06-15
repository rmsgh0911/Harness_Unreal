# CLAUDE.md

This repository uses the Harness workflow.

## Mandatory Startup

Before starting any task:

1. Read the root `HARNESS.md`.
2. Read `Harness/README.md` for the shared and worker-area layout.
3. Read `Harness/Claude/work/state.md` and `Harness/Claude/work/next.md` before project work.
4. Before editing any project file, run this command unless Python is unavailable:
   `python Harness/Claude/scripts/tools/harness_context.py --request "<user request>"`
5. Follow the default Harness loop:
   `implement -> minimal verification -> self-review -> record`.

If the context command cannot run, manually read `HARNESS.md`, `Harness/README.md`, `Harness/Claude/work/state.md`, `Harness/Claude/work/next.md`, and `Harness/Claude/index/project_index.md` when present before editing.

For feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

Before the final response for project changes, check the smallest useful verification result, `git diff --stat`, and whether `Harness/Claude/Progress.md` needs a brief Korean update.

## Defaults

- Do not broadly scan the whole repository.
- Read and edit only files directly relevant to the request.
- Use `Harness/Claude/index/project_index.md` as a routing hint when it exists; verify final assumptions against actual code, config, assets, logs, or build output.
- Prefer one primary worker.
- Do not use external reviewers, summary agents, or multi-agent mode unless the user explicitly asks.
- If unsure, do not skip Harness; run the startup context command above or apply the manual fallback reads.

## Claude Code As Primary Worker

- Claude Code may work as the primary single worker without Codex.
- If the human explicitly switches the primary worker, follow the worker switching rules in `HARNESS.md`.
- When receiving work from another worker, first read `HARNESS.md`, `Harness/Claude/work/state.md`, `Harness/Claude/work/next.md`, today's `Harness/Claude/work/cycles/YYYY-MM-DD.md` if it exists, and the current `git status/diff`.

## Claude Code Notes

- Use planning mode only when the implementation scope is broad or risky. For small fixes with clear scope, proceed directly.
- Treat `Harness/Claude/work/state.md`, `Harness/Claude/work/next.md`, and `Harness/Claude/work/cycles/` as the durable project context. Use Claude memory only as a supplement.
- When referencing files in the worktree, prefer paths relative to the repository root.

## Repository-Specific Additions

Append short repository-specific rules below this section only when needed.
