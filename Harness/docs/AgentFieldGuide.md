# Agent Field Guide

This guide captures practical lessons from applying Harness in real Unreal projects. It is intentionally generic: copy it into a project as a starting checklist, then move project-specific facts into `Harness/index/`, `Harness/work/state.md`, or task records.

## Start From Evidence

- Confirm the actual Unreal project root before searching broadly. Template-only checkouts can look like missing code.
- Run `harness_context.py --request "<request>"` and read only the recommended state, next, task, cycle, or index sections.
- Run `harness_field_check.py` when starting a new project or after a migration. Add `--branches <names...>` only when the project actually needs remote branch alignment evidence.
- Treat indexes, prior notes, and handoffs as pointers. Verify final assumptions against source, config, assets, logs, generated JSON, screenshots, commandlet output, or build results.
- When another agent reports a fact, translate it into a checkable hypothesis. Find the code path or asset state that would make it true.

## Debugging Pattern

- Reproduce the symptom or inspect the exact reference the user gave before patching.
- State the mechanism: what input, binding, actor lifecycle, generated asset, or config path causes the symptom?
- Prefer a narrow fix that changes that mechanism. Avoid broad rewrites, visual-only patches, or duplicated fallback systems unless the existing system cannot support the behavior.
- Make generated data idempotent. Loader or placement scripts should clear, update, or deduplicate their own prior output before adding new rows or actors.
- For Korean text and Windows consoles, verify stored file content or rendered output instead of trusting garbled terminal display.

## Unreal Verification

- C++ or module changes: run the project build wrapper when practical.
- Unreal Python scripts that import `unreal`: run them through `Harness/scripts/tools/harness_unreal_script.py --script <file> --run`.
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
- **Checkout constraint**: A branch already checked out in a worktree cannot be checked out again from another worktree — `git checkout <branch>` will fail with "fatal: already checked out." To sync that branch, run `git -C <worktree-path> reset --hard <commit>` inside its worktree, then push from the worktree or use the worktree path as the push source.
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
- For repeated work, record success criteria, cycle number, changed items, verification, remaining work, and one decision.
- Archive completed task/cycle records when they stop helping current routing.
- If verification passes with warnings, record what the warning means and whether it is baseline/environmental or caused by the current change.

## Git LFS And Binary Assets

- Unreal binary assets (`.uasset`, `.umap`) use Git LFS. Confirm `.gitattributes` is set before committing new asset types.
- LFS uploads for a single push can be 100–300 MB or more. Budget time for pushes that include many new or modified assets.
- Do not stage binary assets that were only modified by editor navigation (camera position, selection state changes). Review `git diff --stat` before staging `.umap` files.
- When a worktree sync involves binary assets, prefer `git -C <worktree> reset --hard <commit>` over a fresh checkout to avoid re-downloading LFS objects.

## Approximate Coordinate Placement From Images

- When exact 3D coordinates are unavailable (e.g., a reference image without coordinate data), accept approximate placement and document the limitation explicitly in the cycle record.
- State the source reference (image filename or screenshot) and the method used (visual estimation, bounding-box mapping, or relative offset from a known anchor).
- Record the approximation in `Remaining:` with a note that precise coordinates require a vendor-supplied data file or on-site measurement.
- Use a consistent naming convention for approximation-sourced items (e.g., `_approx` suffix or a comment in the data) so they can be replaced when exact data arrives.

## Release And Migration Habits

- Treat Harness updates as reviewed migrations. Preserve project-owned config, docs, indexes, work records, Progress, and custom tools.
- Stage template changes for review with `harness_update_plan.py --stage-review <dir>` instead of blindly replacing files.
- Keep template docs generic. Project names, real paths, branch names, credentials, and active work logs belong in the target project, not in the reusable template.
- Before reporting completion, run `harness_verify_all.py`, inspect `git diff --stat`, and confirm generated caches or handoff files were not introduced.
