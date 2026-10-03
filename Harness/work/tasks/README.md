# Task Records

Create one file per task or branch: `Harness/work/tasks/<task-id>.md`.

Copy `task.example.md` and record the owner, branch, worktree, timestamps, status, scope, success criteria, and remaining work. Keep the task ID filesystem-safe and use the same ID with the launcher's `cycle --task` command.

Use a branch-unique task ID when multiple worktrees may create similarly named work.

Keep `Status` (exactly one non-empty field) and `Updated` (at most one) in leading metadata before the first subsection or fenced example. Close/archive never infer completion from examples in the body. Resolve required remaining work before recording `stop_success`; clearly label allowed residual risks instead of claiming they were verified.
