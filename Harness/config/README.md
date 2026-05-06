# Harness Config

This folder stores reusable Harness configuration for the project and supported workers.

- `project.json`: project-specific Unreal verification settings
- `agents.json`: supported workers and their root instruction files
- `cycle_policy.json`: structured helper for the single-worker cycle flow, cycle count interpretation, worker switching, tool additions, and stop conditions
- `docs.json`: project document locations and on-demand reading policy

This folder should contain declarative configuration only. Do not store cycle logs, long reviews, design documents, tokens, API keys, or local credentials here.

Credentials belong to each user's local app, CLI, or agent environment. Harness must not store tokens, API keys, or login data.

## Project Docs

Design docs, implementation specs, simulation scenarios, validation criteria, and retrospectives live under `Harness/docs/` by default.

`docs.json` stores document roots, the policy for when agents should read docs, and request hints. Do not place full design docs under `Harness/config/`.

If docs are too large or the team already has an external docs folder, register root-level `ProjectDocs/`, `Docs/`, or `DesignDocs/`. The default migration unit remains `HARNESS.md` plus `Harness/`.

`Harness/docs/Progress.md` is the default Korean human-facing dashboard. Other Harness operating files should stay in English for agent portability.

## Primary Worker Changes

When working in Codex, `AGENTS.md` is the first root instruction file. When working in Claude Code, `CLAUDE.md` is the first root instruction file.

`agents.json` does not launch agents. It only records which worker reads which root instruction file.

To change the primary worker, the human starts a new session in the target app or CLI.

Worker switching should be explicit. When a switch happens, record the reason and the new worker's first-read files in today's `Harness/cycles/YYYY-MM-DD.md`.
