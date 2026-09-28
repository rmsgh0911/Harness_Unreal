# Agent Field Guide

This guide captures practical lessons from applying Harness in real Unreal projects. It is intentionally generic: copy it into a project as a starting checklist, then move project-specific facts into `Harness/index/`, `Harness/work/state.md`, or task records.

## Start From Evidence

- Confirm the actual Unreal project root before searching broadly. Template-only checkouts can look like missing code.
- Run the launcher's `context --request "<request>"` command and read only the recommended state, next, task, cycle, or index sections.
- Put site-specific additions below the marker in `Harness/config/local_rules.md`; the context briefing routes to that project-owned file only when active rules are present.
- Run the launcher's `field-check` command when starting a new project or after a migration. Add `--branches <names...>` only when the project actually needs remote branch alignment evidence.
- Treat indexes, prior notes, and handoffs as pointers. Verify final assumptions against source, config, assets, logs, generated JSON, screenshots, commandlet output, or build results.
- When knowledge search reports omitted files or 50,000-character truncation, inspect the current task/explicit path first and use the suggested broader bound only when the missing scope matters.
- When another agent reports a fact, translate it into a checkable hypothesis. Find the code path or asset state that would make it true.

## Debugging Pattern

- Reproduce the symptom or inspect the exact reference the user gave before patching.
- State the mechanism: what input, binding, actor lifecycle, generated asset, or config path causes the symptom?
- Prefer a narrow fix that changes that mechanism. Avoid broad rewrites, visual-only patches, or duplicated fallback systems unless the existing system cannot support the behavior.
- Make generated data idempotent. Loader or placement scripts should clear, update, or deduplicate their own prior output before adding new rows or actors.
- For Korean text and Windows consoles, verify stored file content or rendered output instead of trusting garbled terminal display.
- A garbled `Get-Content` result on Windows is usually an output decoding problem, not proof that the file is damaged. Confirm without Python by setting `[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()` and reading `[System.IO.File]::ReadAllText((Resolve-Path 'Harness/Progress.md'), [System.Text.UTF8Encoding]::new($false, $true))` in PowerShell; the strict decoder throws on invalid UTF-8 bytes.
- When a task only needs agent context, prefer English Harness docs and compact indexes. Read Korean files only when they are directly relevant to the user-facing status, copy, or project requirements.

## Text And Encoding

- Keep long-lived agent instructions, indexes, tool docs, tests, and template docs in English unless the project has a specific reason to do otherwise.
- Keep Korean content short and human-facing. `Harness/Progress.md` is the default place for Korean project status; detailed Korean work history should not accumulate there.
- If Korean output looks corrupted, first check whether the bytes decode as UTF-8 and whether replacement characters are actually present. Do not rework content based only on terminal mojibake.
- For PowerShell inspection sessions, use UTF-8 settings when practical:

```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
```

- If tools still disagree, trust source bytes, UTF-8 explicit reads, rendered output, or project verification over console display.

## Unreal Verification

- C++ or module changes: run the project build wrapper when practical.
- Unreal Python scripts that import `unreal`: run them through the launcher's `unreal-script --script <file> --run` command.
- Asset or level state: write a commandlet verifier that checks exact actors, IDs, counts, bindings, or saved status JSON.
- UMG/Blueprint work: verify generated hierarchy, named widget exposure, runtime binding, interaction events, and rendered layout as separate layers.
- UI parity work: compare against the concrete Figma/image/reference files the user named. A popup/detail view should verify selected-record content, not just the existence of a panel.
- Interaction feel, camera, input, animation, and PIE-only behavior may need a manual verification note after automation.

## UMG Widget Visibility: Editor vs PIE

- `AddToViewport()` inside `BeginPlay()` only runs in PIE. Widgets placed this way are **invisible in the editor viewport** — this is expected behavior, not a bug.
- If an actor is named "PreviewActor" but shows nothing in the editor, check whether its widget creation is in `BeginPlay()` (PIE-only) or `OnConstruction()` (editor-visible).
- `ULineBatchComponent` visualizations rebuilt in `OnConstruction()` or `PostEditChangeProperty()` do show in the editor viewport. Use this for 3D debug markers and coordinate grids.
- Always verify the widget/visualization in the correct context: editor viewport for `OnConstruction`, PIE for `BeginPlay`.
- When an integration actor has a flag like `auto_create_dashboard_widget = false`, both the editor and PIE will skip that path — check all actors in the level that could create the same widget independently.

## Actor Positioning Near the Model

- Unreal Python placement scripts may default to world origin `(0, 0, 0)` when position is not explicitly set. Actors at origin are invisible when the main model is at `(20000+, 0, 0)`.
- After placing any reference or UI actor via script, verify its transform in the Details panel or log it in the placement script.
- For screen-space UI actors (widgets via AddToViewport), world position does not affect rendering. For 3D visualization actors, position must be within the visible model bounds.
- When regenerating a level, check that previously placed actor positions are preserved or explicitly reset to the correct location.

## Optional Parallel Worktrees

- A project may use one normal checkout, one extra worktree, many worktrees, or no parallel worktrees at all. Do not invent worktrees because the template mentions them.
- Use separate worktrees only when parallel agents or parallel tasks would otherwise edit the same checkout at the same time.
- **Checkout constraint**: A branch already checked out in a worktree cannot be checked out again from another worktree — `git checkout <branch>` will fail with "fatal: already checked out." Inspect status, branch, HEAD, and the intended commit in that worktree. If it is clean and can fast-forward to a verified descendant, run `git -C <worktree-path> merge --ff-only <verified-commit>` there. Stop for a decision when the worktree is dirty or diverged; never auto-stash or hard-reset user changes.
- **Merge order for sibling branches**: When merging two sibling branches, prefer the one with fewer changes or a clean fast-forward first. Merge the larger/conflicting branch second to reduce conflict surface. After each merge, run the build and primary verifier before merging the next branch.
- Branch and worktree names are project-owned. They might be `feature/login`, `artist/ui-pass`, `release/1.2`, or anything else; never assume `work1` or `work2`.
- When a project does use parallel worktrees, keep one active branch per worktree and inspect every involved checkout with `git status --short --branch` before merge or sync.
- When consolidating sibling work, a dependable flow is: fetch, verify ancestry/diff, merge or fast-forward into the integration branch, run the smallest useful verification, push, then align sibling branches only if requested.
- After pushing a requested branch-family sync, verify the remote refs directly:

```powershell
git ls-remote --heads origin main feature/login release/1.2
```

Use the actual branch names for the project.

## Records That Stay Useful

- `Harness/Progress.md` is a short human dashboard. Keep it to current status, recent completion, confirmation needed, and next work.
- Put detailed work history in task and cycle records, not in `Progress.md`, `state.md`, or `next.md`.
- Use optional `Harness/data/memory/*.jsonl` only for compact reusable lessons or routing hints. Do not copy long logs, private credentials, or unverified agent guesses into memory.
- Rebuild `Harness/data/harness.sqlite` from JSONL shards when search cache behavior looks stale; do not edit or commit the SQLite file.
- For repeated work, record success criteria, cycle number, changed items, verification, remaining work, and one decision.
- Match each important claim to the strongest evidence layer actually checked: source structure, runtime execution, rendered output, user interaction, or a live external service. Do not translate a successful generator or command into visual/interaction acceptance without the relevant artifact and explicit result.
- Record the tested input revision and artifact revision for screenshots, reports, or captures. If later work makes evidence stale, retain it as `Invalidated: true`; a corrected cycle should name the older section under `Supersedes` instead of silently rewriting history.
- When generated evidence must outlive one cycle, add it to `generated_artifacts.json`. Keep outputs and sources project-relative, hash the output bytes, record a timezone-aware generation time and verification command, and rerun `Harness/harness.cmd artifacts` after regeneration; the registry never substitutes for opening a visual artifact or exercising an interaction.
- Close a task only after its latest cycle says `stop_success` with concrete verification. Preview `Harness/harness.cmd close --task <task-id>` before adding `--write`; the write path updates status and archives the pair with rollback on failure.
- If verification passes with warnings, distinguish new debt from an accepted baseline. Baseline only a stable warning ID in `record_policy.json` with a reason and expiry; resolved IDs remain visible for cleanup, and expired entries fail strict checking.

## Git LFS And Binary Assets

- Unreal binary assets (`.uasset`, `.umap`) use Git LFS. Confirm `.gitattributes` is set before committing new asset types.
- LFS uploads for a single push can be 100–300 MB or more. Budget time for pushes that include many new or modified assets.
- Do not stage binary assets that were only modified by editor navigation (camera position, selection state changes). Review `git diff --stat` before staging `.umap` files.
- When a worktree sync involves binary assets, inspect status and ancestry before changing refs. Prefer a clean `git -C <worktree> merge --ff-only <verified-commit>` when possible; if the branch diverged or contains user changes, stop and choose an explicit preservation strategy instead of resetting it.

## Approximate Coordinate Placement From Images

- When exact 3D coordinates are unavailable (e.g., a reference image without coordinate data), accept approximate placement and document the limitation explicitly in the cycle record.
- State the source reference (image filename or screenshot) and the method used (visual estimation, bounding-box mapping, or relative offset from a known anchor).
- Record the approximation in `Remaining:` with a note that precise coordinates require a vendor-supplied data file or on-site measurement.
- Use a consistent naming convention for approximation-sourced items (e.g., `_approx` suffix or a comment in the data) so they can be replaced when exact data arrives.

## Release And Migration Habits

- Treat Harness updates as reviewed migrations. Preserve project-owned config, docs, indexes, work records, Progress, and custom tools.
- Stage template changes for review with the new template launcher's `update --stage-review <dir>` command instead of blindly replacing files.
- Keep template docs generic. Project names, real paths, branch names, credentials, and active work logs belong in the target project, not in the reusable template.
- Before reporting completion, run the launcher's `verify` command, inspect `git diff --stat`, and confirm generated caches or handoff files were not introduced.
