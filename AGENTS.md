# AGENTS.md

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

Keep repository-specific additions short and append them below this section only when needed.
