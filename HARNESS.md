# HARNESS.md

This file defines the default operating rules for agents working with this Unreal Engine Harness template.

## Core Principles

- Default mode is one fast primary worker.
- Default flow is `implement -> minimal verification -> self-review -> record`.
- Do not run external review, external agent checks, or summary agents in the default loop.
- Read and edit only the files that are directly relevant to the current request.
- Prefer evidence from code, config, logs, and command output over assumptions.
- Never revert user changes or unrelated generated files unless the user explicitly asks.

## Startup Read Order

1. Check the project root `README.md` if it exists.
2. Read `Harness/README.md`, `Harness/state.md`, and `Harness/next.md`.
3. If today's `Harness/cycles/YYYY-MM-DD.md` exists, skim the latest entries.
4. If the user asks for cycles, iteration, "up to N times", or "up to N cycles", check `Harness/config/cycle_policy.json`.
5. If the user asks to reference design docs, specs, scenarios, validation criteria, or if the implementation intent is unclear, check `Harness/config/docs.json` and read only the relevant project docs.
6. Inspect only the `Source/`, `Config/`, `Plugins/`, `Content/`, or `Harness/scripts/` files needed for the current request.

## User Request Interpretation

- If the user gives a clear feature name, bug, success criterion, or maximum cycle count, prioritize implementation and verification.
- If success criteria are unclear, infer the smallest reasonable criterion from the current context and continue.
- If the user says "cycle", "iterate", "up to N times", or "up to N cycles", treat the task as Harness cycle work.
- A maximum cycle count is an upper bound, not a required count.
- If no maximum is given, run one cycle by default.
- Stop before the maximum when the success criteria are met and there is no obvious safety improvement left.
- One cycle means `implement or improve -> minimal verification -> self-review -> short record -> decide whether to continue`.
- Do not repeat the same failed attempt without new evidence.
- Stop and report when the same issue repeats twice, the build fails twice for the same reason, the diff becomes unexpectedly large, or a public API / Blueprint risk appears.

Example requests:

- `"Build the inventory UI. Up to 6 cycles."`
- `"Fix the lock-on feature within 4 cycles."`
- `"Keep iterating until the build passes."`

## Feature Work Loop

1. Restate the request, scope, and verification method briefly.
2. Read only the files needed to understand the existing pattern.
3. Check risk before editing.
4. Implement the smallest useful change.
5. Run the smallest reasonable verification command.
6. Self-review the changed files for Unreal-specific risks.
7. Apply one focused safety improvement only if it directly reduces risk.
8. Record manual verification needs for PIE, input feel, HUD, camera, animation, or asset state when automation cannot prove them.

Cycle priority:

1. Make the requested behavior actually work.
2. Fix verification or build failures.
3. Cover empty states, failure states, and input handling.
4. Add stability checks such as null checks, lifecycle cleanup, and delegate cleanup.
5. Keep records short and current.

Do not spend cycle time on wording, formatting, comments, or naming cleanup unless it blocks verification or debugging.

## Project Docs

- Project design docs, implementation specs, simulation scenarios, validation criteria, and retrospectives live under `Harness/docs/` by default.
- `Harness/docs/Progress.md` is the only Harness document that should be written in Korean by default. It is a human-facing dashboard, not a work log. Update it briefly only after major feature completion, before commits, when direction changes, or when human confirmation is needed.
- Keep the template migration unit small: by default, move only `HARNESS.md` and `Harness/`.
- If docs are too large or the team already has an external docs folder, register root-level `ProjectDocs/`, `Docs/`, or `DesignDocs/` in `Harness/config/docs.json`.
- `Harness/config/docs.json` stores doc locations and reading policy only. Do not store full design documents under `Harness/config/`.
- Agents do not read project docs by default. Read them only when requested, when game rules or success criteria are unclear, or when code/config/assets are not enough.
- When reading docs, start from `entry_points` and relevant sections. Do not bulk-read every document.
- If unsure whether docs are needed, run `python Harness/scripts/tools/harness_context.py --request "<request>"` or `python Harness/scripts/tools/harness_docs_check.py --request "<request>"`.
- If project docs conflict with code, config, assets, or build output, report the difference instead of forcing the docs assumption.

## Recording Rules

- `cycles/YYYY-MM-DD.md` contains only short attempts, results, and next actions.
- `state.md` is not a work log. Keep only the latest confirmed facts in present tense.
- `next.md` contains only unresolved work, deferred risks, and human decisions needed.
- `docs/Progress.md` contains a short Korean human summary only. Do not duplicate long content from `state.md`, `next.md`, or `cycles/`.
- Do not duplicate the same details across `state.md`, `next.md`, and `cycles/`.
- When editing the template repository itself, do not create real project cycle logs unless the user explicitly asks.

Recommended cycle log format:

```markdown
## HH:MM Task Name
- Changed:
- Verified:
- Remaining:
```

## Config Files

- `Harness/config/cycle_policy.json` is a structured reference for cycle rules. If it conflicts with this file, `HARNESS.md` wins and the config should be updated.
- `Harness/config/agents.json` maps supported workers to their root instruction files.
- `Harness/config/docs.json` stores project document locations and on-demand reading policy.

## Worker Switching

- Use one primary worker: Codex or Claude Code. Do not use git-worktree multi-agent mode by default.
- Switch workers only when the human explicitly assigns it, Codex token budget is exhausted, or context is too large.
- Worker switching is never automatic.
- Before switching, record the reason and the first files the next worker should read in today's `cycles/YYYY-MM-DD.md`.
- The new worker should first read `HARNESS.md`, `Harness/state.md`, `Harness/next.md`, today's cycle log, and the current `git status/diff`.

## Unreal Cautions

- Edit `Source/` and `Plugins/` only when directly relevant.
- Edit `Config/` only when input, maps, modules, or build settings require it.
- Edit `Content/`, `Build/`, and generated files only when necessary.
- Treat `UFUNCTION`, `UPROPERTY`, public function names, and public variable names as Blueprint compatibility risks.
- Change public API only when required.
- Edit `*.Build.cs` only when required, and check module dependency impact.
- Check include paths, module boundaries, and Public/Private folder placement.
- For UObject, Actor, ActorComponent, and Delegate usage, check null handling and lifecycle.
- When binding delegates, check unbind timing and duplicate binding risk.

## Verification

- Run the smallest useful build or verification command.
- Passing `Harness/scripts/unreal/verify_project.py` alone does not prove feature success.
- When doc policy may matter, run `python Harness/scripts/tools/harness_docs_check.py --json`.
- For C++ or module changes, prefer a real build when practical.
- For build verification, prefer `Harness/scripts/build/build_verify.cmd` or `Harness/scripts/build/build_verify.ps1`.
- If C++ verification fails because the editor is running, DLLs are locked, or hot reload interferes, close the editor and retry a `-NoHotReload` style build.
- Gameplay, input feel, assets, HUD, camera, animation, and level feel may require manual PIE verification. Record that need when automation cannot prove it.
- If a test or verification could not be run, record why.

## Tool Additions

- Agents may add small CLI tools for repeated exploration, verification, summarization, or recording work.
- Put such tools under `Harness/scripts/tools/` by default.
- Tools should have one small purpose and be read-only by default.
- File writes must require explicit options such as `--write`, `--apply`, or `--update`.
- Do not hardcode project-specific values in tool code. Use `Harness/config/project.json` or command-line arguments.
- When adding or changing a tool, update `Harness/scripts/tools/tool_manifest.json` with purpose, inputs, outputs, write behavior, and verification command.
- Verify new or changed tools with `--help`, dry run, JSON output, or the smallest reasonable command.
- Do not create tools for one-off transformations, judgment-heavy refactors, or unstable Unreal Editor internal state.

## Git

- If this is a Git repository, start by checking `git status --short`.
- Do not revert user changes or unrelated changes.
- Generated folders such as `Binaries/`, `Intermediate/`, `Saved/`, and `DerivedDataCache/` are usually not commit targets.
- If `Content/**/*.uasset` or `Content/**/*.umap` changes, record which asset changed and why.
- Do not clean redirectors, move assets, or rename assets unless requested.
- Commit only when the user asks.
- Create branches, rebase, force-push, or rewrite history only when the user explicitly asks.
- Before finishing, inspect `git diff --stat` or the relevant diff and confirm the change scope matches the request.

## Language

- Reply to the user in the user's language.
- Write agent-facing Harness files in English by default for migration stability.
- The default exception is `Harness/docs/Progress.md`, which should be written in Korean because it is a human-facing project dashboard.
- Keep code identifiers, file names, class names, function names, commands, logs, and error messages in their original language.
- When editing non-ASCII files from Windows PowerShell, use explicit UTF-8 handling.
