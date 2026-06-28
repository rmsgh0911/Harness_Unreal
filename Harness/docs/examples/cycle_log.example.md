# Cycle Log Example

Use task-scoped files such as `Harness/work/cycles/<task-id>.md` for parallel work. Date files remain available for simple single-task work. Do not ship real cycle logs in a clean template package.

Each entry records a timezone-aware `Recorded` timestamp, the active worker, cycle number, decision, and success criteria.

## Minimal Entry (single-task, date file)

```markdown
## HH:MM Task Name

- Recorded: YYYY-MM-DDTHH:MM+09:00
- Worker: AgentName
- Cycle: 1
- Decision: stop_success
- Success Criteria: One sentence describing the verifiable outcome.
- Changed: What was added, removed, or modified.
- Verified: What command or check was run and what it confirmed.
- Remaining: What still needs manual PIE/editor inspection or vendor data.
```

## Extended Entry (parallel task, task-scoped file)

```markdown
## HH:MM Feature Description

- Recorded: YYYY-MM-DDTHH:MM+09:00
- Worker: AgentName
- Cycle: 2
- Decision: continue
- Success Criteria: Actor X must appear in level Y with label Z; verifier script must pass with 0 errors.
- Changed: `Source/Module/MyActor.cpp` — added `LoadData()` UFUNCTION; `Harness/scripts/unreal/create_my_level.py` — idempotent actor placement.
- Verified: `build_verify.cmd -Mode Editor` passed (exit 0, 0 errors); `verify_my_level.py` passed 12 checks, 3 actors found.
- Remaining: Manual PIE — confirm widget visible on screen, data binds correctly to selected row.
```

## Decision Values

- `stop_success` — success criteria met; stop here.
- `continue` — criteria not yet met; proceed to next cycle with new evidence.
- `stop_blocked` — blocked by external dependency, environment issue, or repeated failure with no new evidence to try.

## Notes

- Never use `state.md` or `next.md` as an append-only cycle log.
- Keep `Changed` focused on files and mechanism, not intent.
- Keep `Verified` as a concrete command or observable result, not "seems to work."
- `Remaining` should name the exact actor, level, or flow to check manually — avoid generic "test in PIE."
- For PIE-only features (UMG widgets via AddToViewport, input feel, camera), always add a `Remaining` note even when the build passes.
