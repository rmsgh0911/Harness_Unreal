# Harness Work Layer

- `state.md`: latest confirmed project facts only.
- `next.md`: unresolved project-level work and human decisions only.
- `tasks/`: one task/branch record containing owner, branch, worktree, timestamps, status, scope, and remaining work.
- `cycles/`: short task-scoped cycle records. Prefer `<task-id>.md` during parallel work.

`state.md` and `next.md` are consolidation snapshots, not activity logs. During parallel work, the integrator owns these snapshots. Other branches record per-agent and per-edit history in task or cycle files.

Cycle entries may include claim/evidence metadata. Use `structure`, `runtime`, `render`, `interaction`, or `live_service`; visual, interaction, and live-service acceptance requires an artifact. Preserve stale evidence with `Invalidated: true`, and link the correcting entry with `Supersedes`.
