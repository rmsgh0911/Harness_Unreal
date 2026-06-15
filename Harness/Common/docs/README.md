# Harness Docs

This folder is the shared project document root for confirmed design docs, implementation specs, scenarios, validation criteria, and retrospectives.

The default migration unit is `HARNESS.md` plus `Harness/`, so keeping docs here makes the template easier to move between projects.

## Placement Rules

- Put operating rules in the root `HARNESS.md`.
- Put confirmed project reference docs under `Harness/Common/docs/`.
- If docs are too large or the team already uses another docs folder, register root-level `ProjectDocs/`, `Docs/`, or `DesignDocs/` in each worker's `config/docs.json`.
- Agents do not read every doc by default. Read docs only when the user asks, or when implementation intent and success criteria are unclear.

Worker-specific progress dashboards live at `Harness/Codex/Progress.md` and `Harness/Claude/Progress.md`, not in this shared docs folder.

## Expansion Candidates

- `Systems/`: combat, input, interaction, and simulation system specs
- `Scenarios/`: simulation scenarios, test situations, and level intent
- `UX/`: HUD, menus, control flow, and user feedback
- `Validation/`: success criteria, manual verification checklists, and acceptance criteria
- `References/`: external references, retrospectives, and experiment notes

## Document Map

When adding project docs, keep this map short.

- TODO: `Systems/...`
- TODO: `Scenarios/...`
- TODO: `Validation/...`
