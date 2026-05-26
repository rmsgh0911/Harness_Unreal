# Verification Map

Task-type-specific minimum verification guidance. Keep entries short and practical.

## C++ Source Change

Minimum:

- Compile the relevant target when practical.
- Check include and module dependency impact.

## Config Change

Minimum:

- Inspect the changed config key and the runtime path that consumes it.
- Run the smallest relevant project or Harness verification command.

## Blueprint-Facing Change

Minimum:

- Confirm no unintended UFUNCTION or UPROPERTY rename/signature change.
- Record manual PIE verification needs when automation cannot prove behavior.

## Asset, Map, UI, Camera, Or Input Change

Minimum:

- Record the required manual PIE or editor verification.
- Avoid broad asset moves, redirector cleanup, or renames unless explicitly requested.
