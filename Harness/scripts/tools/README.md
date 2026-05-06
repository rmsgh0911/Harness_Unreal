# Harness Tool Repository

This folder contains small CLI tools that agents may add to reduce repeated exploration, verification, summarization, or recording cost.

## Add A Tool When

- The same exploration, verification, summarization, or recording task is likely to repeat.
- The result can be shown as short text or JSON.
- Project-specific values can come from `Harness/config/project.json` or command-line arguments.
- The default behavior is read-only, and file writes require an explicit option.

## Avoid A Tool When

- It is a one-off temporary conversion.
- The work requires heavy judgment or refactoring.
- Reliable results require unstable Unreal Editor internal state.
- Adding an option to an existing script is enough.

## Registration Rules

When adding a tool, update `tool_manifest.json` with:

- `name`: tool name
- `path`: repository-root-relative path
- `purpose`: repeated cost the tool reduces
- `inputs`: main inputs
- `outputs`: main outputs
- `writes_files`: whether it writes files by default or only with explicit options
- `safe_by_default`: whether default execution is read-only and safe on failure
- `verify`: minimal verification command

## Recommended Shape

```powershell
python Harness/scripts/tools/example_tool.py --help
python Harness/scripts/tools/example_tool.py --json
python Harness/scripts/tools/example_tool.py --write
```

Keep tools small. Split them by purpose when they grow.

## Standard Tools

- `harness_context.py`: prints a short Harness briefing for task startup.
- `harness_doctor.py`: checks Harness document, config, and manifest consistency.
- `harness_docs_check.py`: checks `Harness/docs` and `docs.json` discovery / reading policy.
- `harness_scan.py`: summarizes Unreal project structure and `project.json` candidates.
- `harness_cycle.py`: creates cycle log entries; writes only with `--write`. `--changed`, `--verified`, and `--remaining` are repeatable.
- `harness_diff_guard.py`: checks changed files and Unreal risk signals.
- `harness_handoff.py`: creates a minimal handoff brief for another worker or session.
- `harness_verify_all.py`: runs lightweight standard checks before finishing work.
- `harness_migration_audit.py`: audits an older Harness project before migration.
- `harness_state_check.py`: checks whether state/next/cycles are too large, stale, or mixed with history.
- `harness_python_check.py`: checks Python 3 availability and Unreal Python candidates.
- `harness_init_plan.py`: summarizes preservation, fill, and verification work for initialization or migration.
- `harness_docs_index.py`: indexes project doc headings to reduce reading scope.
- `harness_project_fill.py`: creates `project.json` candidates and fills blank fields only with `--write`.
- `harness_cycle_summary.py`: summarizes recent cycle logs.
- `harness_unreal_risk.py`: extracts Unreal-specific risk signals from changed files.
- `harness_unreal_script.py`: checks Unreal Python script readiness and command; runs only with `--run`.

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

`harness_doctor.py` also checks:

- every standard tool is registered in `tool_manifest.json`
- each tool `verify` command references the real tool path
- core `project.json` fields are filled after migration into a real Unreal project
- no generated `__pycache__` or `*.pyc` files remain under `Harness/scripts/`
