# Harness Docs

This folder is the default project document root for design docs, implementation specs, scenarios, validation criteria, and retrospectives.

The default migration unit is `HARNESS.md` plus `Harness/`, so keeping docs here makes the template easier to move between projects.

## Placement Rules

- Put operating rules in the root `HARNESS.md`.
- Put project reference docs under `Harness/docs/`.
- If docs are too large or the team already uses another docs folder, register root-level `ProjectDocs/`, `Docs/`, or `DesignDocs/` in `Harness/config/docs.json`.
- Agents do not read every doc by default. Read docs only when the user asks, or when implementation intent and success criteria are unclear.

## Default File

- `Progress.md`: Korean human-facing dashboard for current goal, status, recent completion, human confirmation, and next decisions.

`Progress.md` is intentionally written in Korean by default. Other Harness files should stay in English for agent portability.

## Expansion Candidates

- `Systems/`: combat, input, interaction, and simulation system specs
- `Scenarios/`: simulation scenarios, test situations, and level intent
- `UX/`: HUD, menus, control flow, and user feedback
- `Validation/`: success criteria, manual verification checklists, and acceptance criteria
- `References/`: external references, retrospectives, and experiment notes

## Document Map

When adding project docs, keep this map short.

- `Progress.md`: Korean human-facing dashboard for progress and confirmation needs
- TODO: `Systems/...`
- TODO: `Scenarios/...`
- TODO: `Validation/...`
