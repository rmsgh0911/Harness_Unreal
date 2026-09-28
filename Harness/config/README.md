# Harness Configuration

- `project.json`: project and Unreal build settings
- `docs.json`: project document locations and on-demand reading policy
- `generated_artifacts.json`: project-owned provenance and integrity records for generated reports, captures, assets, and other evidence
- `cycle_policy.json`: structured cycle, recording, and tool rules
- `agents.json`: supported entry files, shared worktree/task record paths, and provider-neutral read-only subagent roles
- `sensitive_allowlist.json`: hash-only, reasoned, expiring exceptions for the sensitive-data scanner
- `record_policy.json`: optional stable-ID warning baseline; every accepted warning requires a reason and expiry
- `local_rules.md`: short project-, team-, or site-specific rules preserved during template updates
- `template_receipt.example.json`: schema example for the project-owned `template_receipt.json` written only after a verified update

All agents use this single configuration. Worktree branches may change project-specific values only when the branch genuinely requires them.

Subagent prompts live under `Harness/agents/`. Their results are advisory; the primary agent owns edits, durable records, verification decisions, and Git mutations.
