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

Each generated-artifact entry should include `source_sha256`, an object mapping every file in `source_paths` (forward-slash project-relative paths) to its raw SHA-256 at capture time. The checker detects later source changes or deletions even when the output and declared revisions are unchanged. Legacy entries without hashes remain readable with explicit freshness warnings and fail `artifacts --strict`; recapture or verify the evidence before adding current hashes. A malformed hash map is an error. Hash file inputs individually instead of registering directories.

Subagent prompts live under `Harness/agents/`. Their results are advisory; the primary agent owns edits, durable records, verification decisions, and Git mutations.
