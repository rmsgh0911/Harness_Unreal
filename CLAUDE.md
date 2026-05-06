# CLAUDE.md

This repository uses the Harness workflow.

Before starting any task, read the root `HARNESS.md` and follow it.

When the user asks for feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

## Claude Code As Primary Worker

- Claude Code may work as the primary single worker without Codex.
- If the human explicitly switches the primary worker, follow the worker switching rules in `HARNESS.md`.
- When receiving work from another worker, first read `HARNESS.md`, `Harness/state.md`, `Harness/next.md`, today's `Harness/cycles/YYYY-MM-DD.md` if it exists, and the current `git status/diff`.

## Claude Code Notes

- Use planning mode only when the implementation scope is broad or risky. For small fixes with clear scope, proceed directly.
- Treat `Harness/state.md`, `Harness/next.md`, and `Harness/cycles/` as the durable project context. Use Claude memory only as a supplement.
- When referencing files in the worktree, prefer paths relative to the repository root.

## Repository-Specific Additions

Append short repository-specific rules below this section only when needed.
