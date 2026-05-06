# Next

## Immediate Setup Work

- Fill `Harness/config/project.json` for this project.
- Keep project docs under `Harness/docs/` by default. Register external docs folders in `Harness/config/docs.json` only when needed.
- Update `Harness/state.md` from actual Source, Config, and asset evidence.
- If this project will use Git, confirm `.gitattributes` Git LFS rules against team policy.
- Run `Harness/scripts/unreal/verify_project.py` and adapt required checks to the real project.
- If C++ or module work is expected, fill `build.engine_root` and target names so `Harness/scripts/build/build_verify.ps1` can run.
- Create today's `Harness/cycles/YYYY-MM-DD.md` only when real project work should be recorded.

## Feature Work

- TODO: Add feature-sized tasks with success criteria and maximum cycle count when relevant.

## Structure Improvement Candidates

- TODO: Keep candidates small enough for the next cycle.
- TODO: Note how each candidate supports the user's actual goal.
- Treat wording, comments, formatting, and minor renames as low priority unless they block verification or debugging.

## Manual Verification

- TODO: Record PIE checks that automation cannot prove.

## Known Issues

- TODO
