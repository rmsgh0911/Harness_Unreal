# Harness config

This folder contains reusable project and agent settings for Harness.

- `project.json`: Unreal project-specific verification settings.
- `agents.json`: Available AI agents, roles, commands, fallback order, and record paths.
- `cycle_policy.json`: Multi-agent cycle, review, fallback, and stop rules.

Keep this folder declarative. Do not store cycle logs, long reviews, tokens, API keys, or local credentials here.

