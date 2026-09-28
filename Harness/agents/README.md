# Harness Read-Only Subagents

Harness keeps one primary agent as the integration owner. Optional subagents are bounded, read-only helpers: they organize evidence and return advice, while the primary agent verifies claims, edits files, updates durable records, and decides whether work is complete.

Registered roles live in `Harness/config/agents.json`. Their provider-neutral instructions live in this directory so Codex, Claude Code, or another capable local runtime can use the same contract without creating separate Harness trees.

## Invocation

Build a bounded delegation packet before spawning a role:

```powershell
Harness\harness.cmd subagent --role current-status --request "Summarize the current task" --task <task-id>
Harness\harness.cmd subagent --role commit-explainer --request "Prepare the requested commit explanation" --verification "Harness verify passed" --include-staged-patch
```

Use `./Harness/harness.sh` with the same arguments on POSIX. The command does not spawn an agent or write files; it prints the role contract and a read-only evidence packet for the runtime to pass to a subagent. If the runtime has no subagent feature, the primary agent may follow the same contract directly.

The commit packet omits patch text unless `--include-staged-patch` is supplied. That option includes a sensitive-value-redacted excerpt with a 65,536-character default bound; `--max-patch-chars` accepts 1,024-262,144. Treat a truncated excerpt as an explicit evidence gap.

The staged path list defaults to 256 paths independently of the 80-line status summary. To expand an incomplete scope, use `--max-staged-paths <count>` (at most 4096) together with `--expected-snapshot <git.snapshot_id>` from the earlier packet. A changed HEAD, index, or status snapshot rejects the retry. Incomplete scope never becomes ready merely because patch text was requested.

User request and verification fields are bounded and sensitive-value-redacted. If one is truncated or crosses a private-key boundary, collection fails closed and omits the remaining repository evidence instead of risking a cross-field leak.

## Boundaries

- Use only registered roles at their documented checkpoints. Do not invoke them for every small task.
- Pause primary-agent mutation while a status or staged-commit snapshot is being inspected.
- Refresh Git, context, or memory evidence only by asking the primary agent to rebuild the bounded packet; helper roles do not run raw replacement commands.
- Treat subagent output as advisory. Recheck material claims against the cited path or command.
- The primary agent alone updates `state.md`, `next.md`, `Progress.md`, task/cycle records, and completion status.
- The commit role never stages, commits, amends, tags, pushes, or treats unstaged work as part of the proposed commit.
- A request for a commit message alone does not authorize staging or committing. An empty index produces `not_ready`.
- A role that needs to write must stop and return the request to the primary agent. Normal task/worktree rules apply from there.

Read-only roles may share the primary checkout because they do not mutate it. Independent write-capable work still requires a separate worktree and branch.

For an explicitly authorized commit, use this order: memory review and verification, primary agent stages the intended scope, pause mutation and freeze the index, run `commit-explainer`, primary agent rechecks the staged snapshot hash and scope, then commit. A message-only request stops at `not_ready` when nothing is already staged.
