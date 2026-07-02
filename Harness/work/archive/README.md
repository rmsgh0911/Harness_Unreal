# Work Archive

Completed task and cycle records may be moved into monthly folders with `harness_archive.py`.

The command is read-only by default and has two modes:

- `--task <task-id> --archive` moves a completed task record and its task-scoped cycle file. The task record must have a completed status first.
- `--before YYYY-MM --archive` moves date-named cycle files (for example `2026-06-17.md` or `claude-2026-05-08.md`) older than the given month into the monthly folder matching each file's own date.

Monthly folders keep same-named records under separate `tasks/` and `cycles/` folders. `index.md` is generated on the first archive and keeps task IDs and archived cycle months searchable.

Real archive records and the generated archive index are project-owned history. Strict template checks flag them, and release packages exclude them; only this README belongs in a clean template.
