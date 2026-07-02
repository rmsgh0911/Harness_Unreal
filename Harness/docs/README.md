# Project Documents

Store confirmed project design documents, implementation specs, scenarios, and validation criteria here. Register external document roots in `Harness/config/docs.json`.

Agents read docs on demand when requested or when code, config, assets, and logs do not establish intent clearly. `Harness/Progress.md` remains the short Korean human dashboard.

## Template Guidance

- `AgentFieldGuide.md`: field-tested operating habits for Unreal Harness agents.
- `template/first-project-connect.md`: agent checklist for first project connection and post-update readiness.
- `template/gitea-ci.md`: GitHub-compatible, Gitea, and closed-network CI runner modes.
- `template/project-ci.md`: how to attach real Unreal build, commandlet, and PIE verification in target projects.
- `examples/cycle_log.example.md`: example cycle record shape.

## Project Usage

- Add confirmed project documents under `Harness/docs/`.
- Register external document roots in `Harness/config/docs.json`.
- Read docs on demand when the user references specs, designs, checklists, scenarios, validation criteria, or when implementation intent is unclear.
- Keep long retrospectives out of `Progress.md`; summarize durable lessons here or in task/cycle records.
