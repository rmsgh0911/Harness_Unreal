# HARNESS.md

This file defines the default operating rules for agents working with this Unreal Engine Harness template.

## Single Harness, Separate Worktrees

- All agents use the same `Harness/` layout and rules.
- Parallel work must use separate Git worktrees and branches.
- A worktree contains its own copy of `Harness/work/`, so agents do not need separate `Harness/Codex/` or `Harness/Claude/` directories.
- Use one primary agent per task and worktree.
- Never use `state.md` or `next.md` as an append-only agent activity log.

## Core Loop

Default flow: `implement -> minimal verification -> self-review -> record`.

1. Read the root `README.md` when present.
2. Read `Harness/README.md`, `Harness/work/state.md`, and `Harness/work/next.md`.
3. Run `python Harness/scripts/tools/harness_context.py --request "<task>"` when Python is available.
4. Use `Harness/index/project_index.md` as a routing hint, then verify assumptions against actual code, config, assets, logs, or build output.
5. Read project docs only when requested or when success criteria are unclear.
6. Implement the smallest useful change and run the smallest useful verification.
7. Self-review changed files and record only durable information.

Do not broadly scan the repository, run external reviewers, or use multi-agent mode unless the user asks.

## Parallel Work Records

- Create one task file per parallel branch under `Harness/work/tasks/<task-id>.md`.
- Task files should record `Owner`, `Branch`, `Worktree`, `Started`, `Updated`, `Status`, scope, success criteria, and remaining work.
- Prefer task-scoped cycle files under `Harness/work/cycles/<task-id>.md`.
- Run `harness_cycle.py --task <task-id> --worker <agent>` when recording parallel work.
- `Harness/work/state.md` contains only the latest confirmed project facts.
- `Harness/work/next.md` contains only unresolved project-level work and decisions.
- Update `state.md`, `next.md`, and `Progress.md` at integration, handoff, or merge-ready points instead of after every small edit.
- During parallel branch work, the integrator owns consolidation into `state.md` and `next.md`; other branches keep branch-specific details in task and cycle files.
- A short `Last consolidated` and `Consolidated by` header is allowed in `state.md` and `next.md`; per-edit timestamps belong in task or cycle files.
- Do not duplicate the same detail across task files, cycles, state, next, and Progress.

## Cycles

- A cycle means `implement or improve -> minimal verification -> self-review -> short record -> decide whether to continue`.
- A maximum cycle count is an upper bound. Stop early when success criteria are met.
- Do not repeat the same failed attempt without new evidence.
- Stop and report when the same issue repeats twice, a build fails twice for the same reason, the diff becomes unexpectedly large, or a public API / Blueprint risk appears.

Recommended task file:

```markdown
# Task: <task-id>

- Owner: Codex
- Branch: codex/example
- Worktree: C:/path/to/worktree
- Started: 2026-06-15 10:00 +09:00
- Updated: 2026-06-15 10:00 +09:00
- Status: active

## Scope
- ...

## Success Criteria
- ...

## Remaining
- ...
```

Recommended cycle entry:

```markdown
## 10:30 Task Name
- Recorded: 2026-06-15T10:30+09:00
- Worker: Codex
- Changed:
- Verified:
- Remaining:
```

## Project Docs And Index

- Project docs live under `Harness/docs/` by default. Register external doc folders in `Harness/config/docs.json`.
- `Harness/index/` is a compact Project Understanding Layer, not the source of truth.
- Keep `state.md` compact; put project structure and routing notes in `Harness/index/`.
- `Harness/Progress.md` is a short Korean human-facing dashboard, not a work log.

## Harness Updates

- Read `INSTALL.md` before installing, migrating, or updating Harness.
- Treat updates as reviewed migrations, not blind replacement.
- Preserve project-specific config, docs, index, work records, Progress, and custom scripts.
- When migrating from split `Harness/Codex/` and `Harness/Claude/` layouts, merge durable records into the single Harness and preserve conflicting task history as separate task files.

## Tool Additions

- Put repeatable small CLI tools under `Harness/scripts/tools/`.
- Tools should be read-only by default; writes require explicit options such as `--write`, `--apply`, or `--update`.
- Put project-specific values in `Harness/config/project.json` or command-line arguments.
- Update `Harness/scripts/tools/tool_manifest.json` and run the smallest useful verification for changed tools.

## Unreal Cautions

- Edit `Source/`, `Plugins/`, `Config/`, `Content/`, and generated files only when directly relevant.
- Treat `UFUNCTION`, `UPROPERTY`, public names, `*.Build.cs`, delegates, lifecycle, and binary assets as compatibility risks.
- Prefer a real build for C++ or module changes when practical.
- Gameplay, input feel, assets, HUD, camera, animation, and levels may require manual PIE verification.

## Finish Checklist

1. Verify the requested behavior with the smallest useful command or manual check.
2. Inspect `git diff --stat` and confirm the scope matches the request.
3. Refresh `Harness/Progress.md` when meaningful project behavior or a human decision changed.
4. Update the active task file and consolidate durable facts into `state.md` or `next.md` only when appropriate.
5. Run `python Harness/scripts/tools/harness_verify_all.py`.

## Git And Language

- Never revert user changes or unrelated generated files unless explicitly asked.
- Commit, branch, rebase, force-push, or rewrite history only when explicitly asked.
- Reply in the user's language.
- Write agent-facing Harness files in English by default. `Harness/Progress.md` is Korean by default.
