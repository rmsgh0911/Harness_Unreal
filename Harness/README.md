# Harness Folder

The root `HARNESS.md` is the source of truth for operating rules. This file explains the role of the `Harness/` folder and its standard commands.

## Read Order

1. Root `HARNESS.md`
2. `Harness/state.md`
3. `Harness/next.md`
4. Today's `Harness/cycles/YYYY-MM-DD.md` if it exists
5. `Harness/config/cycle_policy.json` when the user asks for cycles, iteration, "up to N times", or "up to N cycles"
6. `Harness/config/docs.json` and relevant docs only when project docs are needed
7. Files directly required by the current request under `Source/`, `Config/`, `Content/`, `Plugins/`, or `Harness/scripts/`

## Folder Roles

- `config/project.json`: project-specific Unreal verification settings
- `config/agents.json`: supported worker to root instruction file mapping
- `config/cycle_policy.json`: structured helper for cycle count interpretation, recording, tool addition, and stop conditions
- `config/docs.json`: project document roots and on-demand reading policy
- `state.md`: latest confirmed project state only
- `next.md`: unresolved work, deferred risks, and human decisions needed
- `cycles/`: short date-based cycle records
- `docs/`: default location for design docs, specs, scenarios, validation criteria, and retrospectives
- `docs/Progress.md`: Korean human-facing dashboard for current progress and confirmation needs
- `scripts/`: Harness script root
- `scripts/unreal/`: Python scripts intended to run inside Unreal Editor
- `scripts/build/`: UBT build and project-file helper scripts
- `scripts/tools/`: small CLI tools that reduce repeated agent work

## Recording Principles

- Keep `cycles/` as short progress records, not a long diary.
- Keep `state.md` to current confirmed facts only.
- Keep `next.md` to work that is still unresolved.
- Keep `docs/Progress.md` in Korean and short. It is for human status review, not agent history.
- Do not duplicate the same details across `state.md`, `next.md`, `cycles/`, and `docs/Progress.md`.
- Before finishing meaningful project work, with or without a commit, check `git diff --stat` and update `docs/Progress.md` if the change affects behavior, assets, captures, maps, verification state, or human decisions.

## Project Docs

Design docs, implementation specs, simulation scenarios, validation criteria, and retrospectives live under `Harness/docs/` by default.

`Harness/docs/Progress.md` is the exception to the English Harness-file rule: write it in Korean because it is a human-facing dashboard. Update it only after major feature completion, before commits, when direction changes, or when human confirmation is needed.

This layout keeps template migration simple: moving `HARNESS.md` and `Harness/` moves the operating rules, state docs, and document map together. If docs are too large or the team already uses an external docs folder, register root-level `ProjectDocs/`, `Docs/`, or `DesignDocs/` in `Harness/config/docs.json`.

Agents read project docs only when the user asks for them or when the task intent cannot be confirmed from code/config/assets alone.

## Verification Tools

- `unreal/verify_project.py`: checks basic project structure, classes, assets, config, and Harness test level readiness
- `unreal/create_level.py`: creates or updates a Harness test level
- `build/build_verify.ps1`: UBT-based build or project-file verification helper
- `build/build_verify.cmd`: Windows wrapper for `build_verify.ps1`
- `tools/tool_manifest.json`: registry of agent-created helper tools and their safety rules

Passing `verify_project.py` does not prove feature success. Add a real build or manual PIE check when the change requires it.

## Cycle Work

When the user asks for "up to N cycles", each cycle means:

`implement or improve -> minimal verification -> self-review -> short record -> decide whether to continue`

The maximum count is an upper bound. Stop early when success criteria are met. Stop and report if the same failure repeats or the diff grows beyond the request.

## Agent Tools

Agents may add small CLI tools under `Harness/scripts/tools/` when repeated exploration, verification, summarization, or recording would otherwise cost tokens.

Standard tools:

- `harness_context.py`: prints a short Harness briefing for task startup
- `harness_doctor.py`: checks Harness structure and config consistency
- `harness_docs_check.py`: checks `Harness/docs` and `docs.json` reading policy
- `harness_scan.py`: summarizes Unreal project structure and `project.json` candidates
- `harness_cycle.py`: creates cycle log entries; writes only with `--write`
- `harness_diff_guard.py`: summarizes changed files and Unreal risk signals, and warns when meaningful project changes are pending without a matching `docs/Progress.md` update
- `harness_handoff.py`: creates a minimal handoff brief; writes only with `--write`
- `harness_verify_all.py`: runs the standard lightweight end-of-task checks
- `harness_migration_audit.py`: audits an older Harness project before migration
- `harness_state_check.py`: checks that state/next/cycles stay compact and current
- `harness_python_check.py`: checks Python 3 availability and Unreal Python candidates
- `harness_init_plan.py`: summarizes preservation, fill, and verification work for initialization or migration
- `harness_docs_index.py`: indexes doc headings before reading full docs
- `harness_project_fill.py`: fills blank `project.json` fields only with `--write`
- `harness_cycle_summary.py`: summarizes recent cycle logs
- `harness_unreal_risk.py`: extracts Unreal-specific risk signals from changed files
- `harness_unreal_script.py`: inspects or runs Unreal Python scripts; runs only with `--run`

Examples:

```powershell
python Harness/scripts/tools/harness_context.py
python Harness/scripts/tools/harness_context.py --request "Improve lock-on input flow"
python Harness/scripts/tools/harness_doctor.py --json
python Harness/scripts/tools/harness_docs_check.py --json
python Harness/scripts/tools/harness_scan.py --json
python Harness/scripts/tools/harness_cycle.py "Input fix" --changed "..." --verified "..." --remaining "..."
python Harness/scripts/tools/harness_diff_guard.py
python Harness/scripts/tools/harness_handoff.py --request "Continue lock-on work"
python Harness/scripts/tools/harness_verify_all.py
python Harness/scripts/tools/harness_migration_audit.py --target C:\Path\To\OldProject
python Harness/scripts/tools/harness_state_check.py --target C:\Path\To\Project
python Harness/scripts/tools/harness_python_check.py
python Harness/scripts/tools/harness_init_plan.py
python Harness/scripts/tools/harness_docs_index.py
python Harness/scripts/tools/harness_project_fill.py --json
python Harness/scripts/tools/harness_cycle_summary.py
python Harness/scripts/tools/harness_unreal_risk.py
python Harness/scripts/tools/harness_unreal_script.py --script Harness/scripts/unreal/verify_project.py
```

If `python` resolves to the Microsoft Store alias on Windows, use the real Python 3 executable or the workspace runtime Python path.

## Template Quality Checks

`harness_doctor.py` checks more than file existence:

- every standard tool is registered in `tool_manifest.json`
- each tool `verify` command points at the actual tool path
- `project.json` can stay blank in the standalone template but should be filled after migration
- no generated `__pycache__` or `*.pyc` files remain under `Harness/scripts/`
