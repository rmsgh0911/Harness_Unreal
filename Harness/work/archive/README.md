# Work Archive

Completed task and cycle records may be moved into monthly folders with `harness_archive.py`.

The command is read-only by default. Use `--archive` only after the task record has a completed status. Monthly folders keep same-named records under separate `tasks/` and `cycles/` folders. `index.md` is generated on the first archive and keeps task IDs searchable.

Real archive records and the generated archive index are project-owned history. Strict template checks flag them, and release packages exclude them; only this README belongs in a clean template.
