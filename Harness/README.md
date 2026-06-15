# Harness Folder

The root `HARNESS.md` defines shared operating rules. This folder separates shared material from worker-specific operating environments.

## Layout

- `Common/`: stable shared policies and confirmed project documents
- `Codex/`: Codex config, scripts, index, Progress dashboard, and work records
- `Claude/`: Claude Code config, scripts, index, Progress dashboard, and work records

Each worker owns its area. Do not automatically synchronize worker files or let one worker write into the other worker's area.

## Entry Routing

- `AGENTS.md` routes Codex to `Harness/Codex/`.
- `CLAUDE.md` routes Claude Code to `Harness/Claude/`.
- Both workers read the shared root `HARNESS.md` and may read `Harness/Common/docs/` on demand.

## Worker Read Order

For the active worker:

1. Root `HARNESS.md`
2. `Harness/<Worker>/work/state.md`
3. `Harness/<Worker>/work/next.md`
4. Today's `Harness/<Worker>/work/cycles/YYYY-MM-DD.md` when present
5. Relevant worker config and index files
6. Shared project docs only when requested or needed

## Standard Commands

Codex:

```powershell
python Harness/Codex/scripts/tools/harness_context.py --request "<task description>"
python Harness/Codex/scripts/tools/harness_verify_all.py
```

Claude Code:

```powershell
python Harness/Claude/scripts/tools/harness_context.py --request "<task description>"
python Harness/Claude/scripts/tools/harness_verify_all.py
```

Each worker maintains its own tool manifest, project config, indexes, work records, and Korean `Progress.md`.

## Shared Material

`Harness/Common/` should stay small. Promote material there only when it is stable, worker-independent, and approved for shared use.
