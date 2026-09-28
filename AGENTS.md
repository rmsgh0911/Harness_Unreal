# AGENTS.md

This repository uses the Harness workflow.

## Mandatory Startup

Before starting any task:

1. Before editing any project file, run this command unless Python is unavailable:
   `& Harness\harness.ps1 context --request "<user request>"` in Windows PowerShell, or `sh Harness/harness.sh context --request "<user request>"` on POSIX. Do not pass free-form request text through the Windows batch wrapper because CMD reparses metacharacters before the wrapper can preserve them.
   Add `--task <task-id>` when working from a parallel task record.
   Direct `python Harness/scripts/tools/harness_context.py ...` remains a supported fallback.
   If Python is unavailable, run `& Harness\harness.ps1 bootstrap` or `sh Harness/harness.sh bootstrap` only when project policy permits its explicit runtime download; otherwise use the manual fallback below.
2. Read only the files and sections the context briefing recommends. It includes `HARNESS.md` and `Harness/README.md` when the task needs them.
   Treat `Harness/config/local_rules.md` as project-owned additions when the briefing routes to it; do not copy those rules back into the reusable template.
3. Open `HARNESS.md` yourself when the briefing did not recommend it but rules feel unclear, the work involves cycles/iteration budgets, or you are about to finish and record.
4. Follow the default Harness loop:
   `implement -> minimal verification -> self-review -> record`.

If the context command cannot run, manually read `HARNESS.md`, `Harness/README.md`, `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` when present before editing.

Read `Harness/docs/AgentFieldGuide.md` when starting a new project, updating/migrating Harness, debugging a repeated failure, changing Unreal UI/asset generation flows, or coordinating branch/worktree sync.

For feature work, bug fixes, verification, cycles, iteration, "up to N times", or "up to N cycles", apply the work loop and recording rules in `HARNESS.md`.

For repeated work, establish success criteria and the cycle budget before editing. Each cycle must add a change or new evidence, run the smallest useful verification, record a continue/stop decision, and avoid reopening settled scope without a new reason. For task-scoped or three-plus-cycle work, run the launcher's `iteration-status` command before continuing.

When updating an older Harness install, run the new template launcher's `migration-audit --target <project>` and `update --target <project>` commands before copying files. Preserve project-owned config, docs, indexes, work records, Progress, and custom tools; use the target launcher's `knowledge --query "<request>"` command to route into retained material after the update.

After first install or Harness update, run `& Harness\harness.ps1 readiness --strict` before declaring the project connected. Routine `verify` runs this non-strict, so only hard connection/config errors block everyday work.

When a defined checkpoint would benefit from a read-only helper, use `& Harness\harness.ps1 subagent --role current-status --request "<request>"` or `& Harness\harness.ps1 subagent --role commit-explainer --request "<request>" --include-staged-patch`, then pass the packet to the runtime's subagent mechanism. Follow `HARNESS.md` and `Harness/agents/`: the primary agent remains the integration owner, and helper output is advisory.

Before the final response for project changes, check the smallest useful verification result, `git diff --stat`, and whether `Harness/Progress.md` needs a brief Korean update. For requested commit or push closeout, run the launcher's `memory-review` command before staging; `local-gate` includes this check for no-CI projects. If the target Gitea repository has no Actions or registered runners, use `& Harness\harness.ps1 local-gate` as the local finish gate before commit or push.

## Defaults

- Do not broadly scan the whole repository.
- Read and edit only files directly relevant to the request.
- Use `Harness/index/project_index.md` as a routing hint when it exists; verify final assumptions against actual code, config, assets, logs, or build output.
- Prefer one primary worker.
- Do not use external reviewers, write-capable helpers, or unrestricted multi-agent mode unless the user explicitly asks. The registered read-only helper roles are allowed only at their defined checkpoints.
- If unsure, do not skip Harness; run the startup context command above or apply the manual fallback reads.

Keep repository-specific additions short and append them below this section only when needed.
