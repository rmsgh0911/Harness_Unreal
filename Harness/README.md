# Harness Folder

This Harness layout works for both a single normal checkout and optional parallel Git worktrees.

All supported agents use this single Harness layout. If a project uses parallel agents or parallel tasks, isolate that work with Git worktrees and branches instead of agent-specific Harness directories. A simple project can use one normal checkout.

## Layout

- `config/`: project, docs, cycle, and agent configuration
- `agents/`: provider-neutral contracts for bounded read-only subagent roles
- `data/`: optional daily JSONL memory shards, examples, schema, and ignored local SQLite cache
- `docs/template/`: template-owned setup and provenance
- `docs/project/`: the default project-owned documentation root
- `index/`: compact project routing maps
- `scripts/tools/`: template-owned Harness tools
- `scripts/project/`: project-owned utilities and a separate manifest
- `template/manifest.json`: deterministic release inventory, hashes, and ownership rules
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
& Harness\harness.ps1 bootstrap
& Harness\harness.ps1 context --request "<task description>"
& Harness\harness.ps1 artifacts
& Harness\harness.ps1 cycle "Task Name" --task <task-id> --worker <agent>
& Harness\harness.ps1 close --task <task-id>
& Harness\harness.ps1 iteration-status --request "<repeated task>" --task <task-id>
& Harness\harness.ps1 readiness --strict
& Harness\harness.ps1 verify
& Harness\harness.ps1 local-gate
& Harness\harness.ps1 handoff --request "<handoff summary>"
& Harness\harness.ps1 subagent --role current-status --request "<status checkpoint>"
& Harness\harness.ps1 subagent --role commit-explainer --request "<commit request>" --verification "<command and result>" --include-staged-patch
& Harness\harness.ps1 update --target C:\Path\To\OlderProject
```

Use `bootstrap` only when Python 3.10+ is unavailable. It is implemented by the native Windows/POSIX launcher, so it works before Python exists; normal commands disable Python Install Manager automatic installation and never download anything implicitly. The explicit bootstrap pins and verifies the `uv` 0.12.18 installer, installs the current patched Python 3.12 build into the platform-specific ignored `Harness/.runtime/` tree, and leaves PATH, shell profiles, and the Windows Python registry unchanged. `bootstrap --status` and reuse of a valid runtime are network-free. An explicit `HARNESS_UV` must also be uv 0.12.18; for offline installation, preseed `UV_CACHE_DIR` or `HARNESS_UV_CACHE_DIR` or configure an environment-based uv Python mirror. Use `HARNESS_RUNTIME_ROOT` to relocate one platform's managed runtime.

Use the PowerShell launcher on Windows, especially for free-form request text: CMD reparses metacharacters before `harness.cmd` can preserve them, so the batch wrapper is only a fixed-token convenience entry point. Use `sh Harness/harness.sh` with the same subcommands on Linux or macOS; this form does not depend on a Git executable bit. Runtime precedence is explicit `HARNESS_PYTHON`, a valid managed-runtime marker, then standard PATH commands. An invalid explicit `HARNESS_PYTHON` fails clearly instead of silently selecting another runtime. Every registered standard tool has a launcher alias; the managed runtime is deliberately not added to PATH. Direct Python tool paths remain compatible only when automation already supplies an interpreter.

Use the rest of the tools as focused diagnostics, migration helpers, or optional project features.

The `subagent` command prints a bounded role-and-evidence packet without writing files or starting a provider-specific agent. Pass it to the runtime's subagent mechanism. The primary agent remains the sole integration and durable-record owner; the commit role treats only staged changes as commit scope and returns `not_ready` when staging is empty. Staged patch text is omitted by default; use `--include-staged-patch` for a redacted excerpt bounded to 65,536 characters, or lower/raise that bound within 1,024-262,144 using `--max-patch-chars`.

Use the launcher's `local-gate` command instead of server CI when a private Gitea project has no Actions or registered runners. It runs the local test/verify finish gate, checks staged and unstaged diff hygiene separately, reports conflicts and untracked files, and is read-only by default. Pass `--cleanup-caches` only when generated Harness Python caches should be removed explicitly.

Use the launcher's `readiness --strict` command at the connection milestone (after first install or Harness update). Inside routine `verify` it runs non-strict: hard connection/config errors block, while lingering template placeholders are non-blocking warnings until you run it with `--strict`.

## Supporting Commands

```powershell
& Harness\harness.ps1 context --request "<task description>" --task <task-id>
& Harness\harness.ps1 context --request "<task description>" --all-next
& Harness\harness.ps1 iteration-status --request "<repeated task>" --task <task-id>
& Harness\harness.ps1 knowledge --query "<feature or issue>"
& Harness\harness.ps1 memory --query "<feature or issue>" --limit 5
& Harness\harness.ps1 progress --write
& Harness\harness.ps1 progress --serve
```

Use the context briefing first, then open only the recommended sections or files. Read the full state, next, and index files only when Python is unavailable, the briefing reports a conflict, or the request needs broader project context.

Cycle records may attach claims to `structure`, `runtime`, `render`, `interaction`, or `live_service` evidence. Rendered, interaction, and live-service claims need a stable artifact before they can be accepted; record matching input/artifact revisions so stale screenshots or reports are visible. Older records without these fields remain readable as legacy evidence.

Task closeout previews by default. After the last cycle says `stop_success` and records concrete verification, add `--write` to mark the task completed and archive its task/cycle pair transactionally. Launcher `state-check --strict` blocks warning IDs that are new or whose reasoned baseline entry has expired.

`generated_artifacts.json` is an empty, project-owned registry until a project chooses to retain generated evidence. Each entry binds an output hash to its generator/revision, sources, matching input/artifact revision, scope, acceptance, and verification command. The aggregate verifier checks it, while strict release hygiene also rejects pending or stale registered evidence.

Use the launcher's `memory` command only for compact routing hints that still need confirmation against source, config, assets, logs, docs, or verification output. `Progress_index.html` is a stable viewer; routine status changes should update `Progress.md` and then reload the viewer. Because browsers block local `fetch()` over `file://`, open the viewer live with `Progress_view.cmd` or the launcher's `progress --serve` command.

For parallel work, create a separate worktree and branch only when the task actually needs parallel isolation, then create `Harness/work/tasks/<task-id>.md`. Keep agent names and timestamps there rather than repeatedly editing shared `state.md` or `next.md`.

## Field Guide

Read `Harness/docs/AgentFieldGuide.md` when starting a new project, onboarding a new agent, debugging a repeated failure, or coordinating optional parallel worktrees. It captures the practical checks that prevent common Unreal Harness mistakes: wrong project root, unverified handoff claims, non-idempotent generated data, UI checks that miss runtime binding, and branch syncs that stop before remote refs are aligned.
