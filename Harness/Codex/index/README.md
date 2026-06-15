# Harness Index Layer

The index layer stores compact project-understanding maps that reduce repeated exploration.

Index files are routing hints, not the source of truth. If an index file conflicts with code, config, assets, build output, or logs, trust the actual project files and report the stale index.

## Standard Files

- `project_index.md`: short human-readable project map.
- `api_surface.md`: Blueprint-facing APIs, integration names, topics, and other compatibility-sensitive names.
- `verification_map.md`: task-type-specific minimum verification guidance.
- `source_map.json`: optional generated source/module map.

Read only the index files relevant to the current request. Do not load the full index by default.
