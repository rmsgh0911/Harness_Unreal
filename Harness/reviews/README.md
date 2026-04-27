# Harness reviews

Use this folder for external AI review context and review outputs.

Recommended naming:

```text
YYYY-MM-DD-task-name-cycle-01-review-context.md
YYYY-MM-DD-task-name-cycle-01-gemini-review.md
YYYY-MM-DD-task-name-cycle-02-codex-review.md
```

Keep `cycles/` short. Put current facts in `state.md`, future work in `next.md`, and detailed reviewer handoff text here.

A review context file should usually include:

- Task goal
- Cycle number
- Worker and reviewer
- Changed files
- Change summary
- Verification result
- Known risks
- Review request

Language:

- Write review context in Korean when the user is working in Korean.
- Raw external review output may keep its original language.
- Summaries copied into `state.md`, `next.md`, or `cycles/` should be Korean.
- Keep code identifiers, file paths, commands, logs, and error messages in their original language.
