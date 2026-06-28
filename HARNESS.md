# HARNESS.md

This file defines the default operating rules for agents working with this Unreal Engine Harness template.

## Single Harness, Optional Worktrees

- All agents use the same `Harness/` layout and rules.
- Projects may use one normal checkout or multiple Git worktrees. Do not create worktrees unless parallel work needs isolation.
- Parallel work, when used, must use separate Git worktrees and branches.
- A worktree contains its own copy of `Harness/work/`, so agents do not need separate `Harness/Codex/` or `Harness/Claude/` directories.
- Use one primary agent per task and checkout/worktree.
- Never use `state.md` or `next.md` as an append-only agent activity log.

## Core Loop

Default flow: `implement -> minimal verification -> self-review -> record`.

1. Read the root `README.md` when present and the short operating rules in `Harness/README.md`.
2. Run `python Harness/scripts/tools/harness_context.py --request "<task>"` when Python is available.
3. Read only the state, next, task, cycle, or index sections recommended by the context briefing. If the command cannot run, read `Harness/work/state.md`, `Harness/work/next.md`, and `Harness/index/project_index.md` manually.
4. Use `Harness/index/` only as a routing hint, then verify assumptions against actual code, config, assets, logs, or build output.
5. Read project docs only when requested or when success criteria are unclear.
6. Implement the smallest useful change and run the smallest useful verification.
7. Self-review changed files and record only durable information.

Do not broadly scan the repository, run external reviewers, or use multi-agent mode unless the user asks.

## Field-Proven Operating Habits

- Verify the real project root before deep search. If a checkout contains only Harness/template files, stop and locate the actual Unreal project before concluding that code or assets are missing.
- Treat Harness indexes and prior notes as routing hints only. Confirm behavior against source, config, assets, generated JSON, logs, screenshots, build output, or Unreal commandlet output.
- When a bug is reported from UI, design, runtime, or another agent's note, first identify the mechanism that could produce the symptom. Prefer a narrow mechanism-correct fix over a visual or string-only patch.
- For Unreal Python, run scripts through `harness_unreal_script.py --script <file> --run` unless the script is explicitly plain CPython. A script that imports `unreal` is not verified by running `python script.py`.
- For UI and Blueprint/UMG work, verify the layers separately when possible: generated asset/tree structure, named widget exposure, runtime data binding, rendered layout, and interaction/event wiring.
- For generated level or asset data, make population scripts idempotent. Remove or reconcile prior generated rows/actors before appending new ones, and verify exact expected IDs or counts.
- If a command reports an environment warning or known baseline issue, separate that signal from the requested change. Record the residual risk instead of hiding or over-fixing it.
- **PIE vs editor distinction**: When a user reports that a dashboard, widget, or UI panel is "not visible," first check whether the relevant actor uses `BeginPlay` or `OnConstruction`. `BeginPlay`-based actors require PIE; confirming "not visible" in the editor viewport is not a bug.
- **Asset path versioning**: Level generation scripts may reference asset paths that have been renamed or versioned. Always verify the exact asset path against the Content Browser or `EditorAssetLibrary.does_asset_exist()` before running a placement script.
- **Widget actor position does not affect screen-space UI**: For actors that call `AddToViewport()`, world position (even if `(0,0,0)`) does not affect visibility. If a screen-space widget is not showing in PIE, check widget class, data asset assignments, and `ZOrder`, not the actor's transform.

## Parallel Work Records

- Create one task file per parallel branch under `Harness/work/tasks/<task-id>.md`.
- Task files should record `Owner`, `Branch`, `Worktree`, `Started`, `Updated`, `Status`, scope, success criteria, and remaining work.
- Prefer task-scoped cycle files under `Harness/work/cycles/<task-id>.md`.
- Run `harness_cycle.py --task <task-id> --worker <agent>` when recording parallel work.
- `Harness/work/state.md` contains only the latest confirmed project facts.
- `Harness/work/next.md` contains only unresolved project-level work and decisions.
- Keep `state.md` near 80 lines or fewer and limited to Project, Current State, Latest Verification, and Risks.
- Keep `next.md` to the 3-5 highest-priority active project items. Remove completed work immediately; move optional ideas to a project backlog document when needed.
- Update `state.md`, `next.md`, and `Progress.md` at integration, handoff, or merge-ready points instead of after every small edit.
- During parallel branch work, the integrator owns consolidation into `state.md` and `next.md`; other branches keep branch-specific details in task and cycle files.
- Archive completed task/cycle pairs with `harness_archive.py --task <task-id> --archive` when history becomes noisy. The command previews by default and preserves task-ID lookup in `Harness/work/archive/index.md`.
- A short `Last consolidated` and `Consolidated by` header is allowed in `state.md` and `next.md`; per-edit timestamps belong in task or cycle files.
- Do not duplicate the same detail across task files, cycles, state, next, and Progress.

## Cycles

- A cycle means `implement or improve -> minimal verification -> self-review -> short record -> decide whether to continue`.
- Before the first cycle, state the success criteria and requested cycle budget. Treat `N cycles` / `N times` as an exact requested count; treat `up to N`, `maximum N`, or similar wording as an upper bound.
- Every cycle must add a meaningful change or new evidence and end with one decision: `continue`, `stop_success`, or `stop_blocked`.
- For task-scoped or three-plus-cycle work, run `harness_iteration_status.py --request "<request>" --task <task-id>` before the next cycle. Do not continue past a stop recommendation without new evidence or a corrected record.
- An upper-bound cycle budget may stop early when success criteria are met. An exact-count cycle budget should continue until the requested count is complete unless a stop condition triggers.
- Do not repeat the same failed attempt without new evidence.
- Stop and report when the same issue repeats twice, a build fails twice for the same reason, the diff becomes unexpectedly large, or a public API / Blueprint risk appears.
- Keep repeated-work records machine-readable: success criteria, cycle number, verification result, remaining work, and one decision (`continue`, `stop_success`, or `stop_blocked`).

Recommended task file:

```markdown
# Task: <task-id>

- Owner: <AgentName>
- Branch: <agent>/example
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
- Worker: <AgentName>
- Changed:
- Verified:
- Remaining:
```

## Project Docs And Index

- Project docs live under `Harness/docs/` by default. Register external doc folders in `Harness/config/docs.json`.
- `Harness/index/` is a compact Project Understanding Layer, not the source of truth.
- Keep `state.md` compact; put project structure and routing notes in `Harness/index/`.
- `Harness/Progress.md` is a short Korean human-facing dashboard, not a work log. Keep only Current Status, Recent Completion, Needs Confirmation, and Next Work, with at most three core bullets per section and about 40 lines total.

## Harness Updates

- Read `INSTALL.md` before installing, migrating, or updating Harness.
- Treat updates as reviewed migrations, not blind replacement.
- Preserve project-specific config, docs, index, work records, Progress, and custom scripts.
- Run the new template's `harness_update_plan.py --target <project>` before copying. `--apply-missing` may add absent files but never overwrites; `--stage-review <dir>` transactionally places changed template files outside both the template and target trees for review.
- After migration, run `harness_knowledge.py --query "<current request>"` so retained docs, task/cycle history, archives, and indexes remain discoverable without broad scans.
- When migrating from split `Harness/Codex/` and `Harness/Claude/` layouts, merge durable records into the single Harness and preserve conflicting task history as separate task files.
- Do not delete the source template folder from a project until the migrated Harness verifies successfully and `git diff --stat` shows only the intended migration.

## Tool Additions

- Put repeatable small CLI tools under `Harness/scripts/tools/`.
- Tools should be read-only by default; writes require explicit options such as `--write`, `--apply`, or `--update`.
- Put project-specific values in `Harness/config/project.json` or command-line arguments.
- Update `Harness/scripts/tools/tool_manifest.json` and run the smallest useful verification for changed tools.
- Prefer adding a small check to an existing finish gate before creating a broad new workflow. Field-proven checks that catch repeated mistakes belong in `harness_field_check.py` or another read-only tool.

## Unreal Cautions

- Edit `Source/`, `Plugins/`, `Config/`, `Content/`, and generated files only when directly relevant.
- Treat `UFUNCTION`, `UPROPERTY`, public names, `*.Build.cs`, delegates, lifecycle, and binary assets as compatibility risks.
- Prefer a real build for C++ or module changes when practical.
- Gameplay, input feel, assets, HUD, camera, animation, and levels may require manual PIE verification.
- Use the smallest useful Unreal verification path: build for C++/module risk, commandlet scripts for asset or level state, screenshot/render checks for UI/layout, and manual PIE notes for interaction feel that automation cannot prove.
- For Git LFS assets, confirm `.gitattributes` and include newly generated docs/assets only when they are part of the requested deliverable. Binary uasset/umap LFS uploads can be 100–300 MB per push; budget time accordingly.
- **Non-ASCII project paths**: If the project directory contains Korean or other non-ASCII characters, UBT's git blame parser may crash. Apply `git config core.quotePath false` once in the repository (stored in `.git/config`) and record it in `Harness/work/state.md` under Risks. Remind users to re-apply after a fresh clone.
- **UMG widget visibility**: `AddToViewport()` inside `BeginPlay()` is PIE-only. Widgets added this way are never visible in the editor viewport. Use `OnConstruction()` or `PostEditChangeProperty()` for editor-visible debug overlays. Document which actors require PIE to see their output.
- **Worktree checkout constraint**: A branch checked out in a worktree cannot be checked out from another tree. Use `git -C <worktree-path> reset --hard <target>` to sync a worktree branch without a fresh checkout.

## Finish Checklist

1. Verify the requested behavior with the smallest useful command or manual check.
2. Inspect `git diff --stat` and confirm the scope matches the request. Do not stage `.umap` files changed only by editor navigation (camera/selection state) unless the level content genuinely changed.
3. Refresh `Harness/Progress.md` when meaningful project behavior or a human decision changed. `Progress.md` is Korean by default; keep it to ~40 lines covering Current Status, Recent Completion, Needs Confirmation, and Next Work.
4. Update the active task file and consolidate durable facts into `state.md` or `next.md` only when appropriate.
5. Run `python Harness/scripts/tools/harness_verify_all.py`.
6. For requested branch-family or worktree syncs, confirm each involved checkout/worktree is clean enough for the operation and verify remote refs after push with `git ls-remote --heads origin <branches...>`.
7. For C++ changes that affect actor visualization or widget behavior, add a `Remaining` note specifying what to confirm in PIE or the editor viewport. Do not claim visual correctness from a build pass alone.
8. For Unreal Python scripts that place or update actors, confirm the script runs idempotently: a second run should produce the same actor count and state, not duplicates.

## Git And Language

- Never revert user changes or unrelated generated files unless explicitly asked.
- Commit, branch, rebase, force-push, or rewrite history only when explicitly asked.
- Reply in the user's language.
- Write agent-facing Harness files in English by default. `Harness/Progress.md` is Korean by default.
