# Harness Configuration

- `project.json`: project and Unreal build settings
- `docs.json`: project document locations and on-demand reading policy
- `cycle_policy.json`: structured cycle, recording, and tool rules
- `agents.json`: supported entry files and shared worktree/task record paths

All agents use this single configuration. Worktree branches may change project-specific values only when the branch genuinely requires them.
