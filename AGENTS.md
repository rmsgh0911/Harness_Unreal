# AGENTS.md

This repository uses the Harness workflow.

## Mandatory Startup

Before starting any task:

1. Before editing any project file, run this command unless Python is unavailable:
   `python Harness/scripts/tools/harness_context.py --request "<user request>"`
   Add `--task <task-id>` when working from a parallel task record.
2. Read only the files and sections the context briefing recommends. It includes `HARNESS.md` and `Harness/README.md` when the task needs them.
3. Open `HARNESS.md` yourself when the briefing did not recommend it but rules feel unclear, the work involves cycles/iteration budgets, or you are about to finish and record.
4. Follow the default Harness loop:
   `implement -> minimal verification -> self-review -> record`.

If the context command cannot run, manually read `HARNESS.md`, `Harness/README.md`, `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` when present before editing.

Read `Harness/docs/AgentFieldGuide.md` when starting a new project, updating/migrating Harness, debugging a repeated failure, changing Unreal UI/asset generation flows, or coordinating branch/worktree sync.

For feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

For repeated work, establish success criteria and the cycle budget before editing. Each cycle must add a change or new evidence, run the smallest useful verification, record a continue/stop decision, and avoid reopening settled scope without a new reason. For task-scoped or three-plus-cycle work, check `harness_iteration_status.py` before continuing.

When updating an older Harness install, run `harness_update_plan.py` from the new template before copying files. Preserve project-owned config, docs, indexes, work records, Progress, and custom tools; use `harness_knowledge.py --query "<request>"` to route into retained material after the update.

After first install or Harness update, run `python Harness/scripts/tools/harness_project_readiness.py --strict` before declaring the project connected. Routine `harness_verify_all.py` runs this non-strict, so only hard connection/config errors block everyday work.

Before the final response for project changes, check the smallest useful verification result, `git diff --stat`, and whether `Harness/Progress.md` needs a brief Korean update. For requested commit or push closeout, review compact memory candidates with `python Harness/scripts/tools/harness_memory_review.py` before staging; `harness_local_gate.py` includes this check for no-CI projects. If the target Gitea repository has no Actions or registered runners, use `python Harness/scripts/tools/harness_local_gate.py` as the local finish gate before commit or push.

## Defaults

- Do not broadly scan the whole repository.
- Read and edit only files directly relevant to the request.
- Use `Harness/index/project_index.md` as a routing hint when it exists; verify final assumptions against actual code, config, assets, logs, or build output.
- Prefer one primary worker.
- Do not use external reviewers, summary agents, or multi-agent mode unless the user explicitly asks.
- If unsure, do not skip Harness; run the startup context command above or apply the manual fallback reads.

Keep repository-specific additions short and append them below this section only when needed.
