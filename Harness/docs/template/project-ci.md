# Project CI Attachment

The template CI proves that Harness itself is healthy. A real Unreal project needs an additional project CI layer because the template repository cannot know the target engine path, plugins, maps, automation tests, or packaging rules.

## Verification Tiers

Use the strongest tier that the target project can run reliably.

### Tier 0: Harness Package

Run this in the template repository and in every target project:

```powershell
python -B -m unittest discover -s Harness/scripts/tools/tests -p "test_*.py"
python Harness/scripts/tools/harness_verify_all.py
```

This catches Harness structure, docs, indexes, progress format, Python syntax, release hygiene, and standard tool regressions. It does not prove Unreal gameplay behavior.

### Tier 1: Unreal Build Readiness

Use this in a real project after `Harness/config/project.json` is filled and `template_mode` is `false`:

```powershell
python Harness/scripts/tools/harness_context.py --request "project CI"
python Harness/scripts/tools/harness_unreal_script.py --script Harness/scripts/unreal/verify_project.py
powershell -ExecutionPolicy Bypass -File Harness/scripts/build/build_verify.ps1 -Mode Editor
```

This tier proves that Harness can locate the project and that the configured editor target can build. Run it on a Windows runner when possible.

### Tier 2: Commandlet Or Map Smoke

Add a project-owned smoke script or commandlet when the project has stable maps, required plugins, or generated data:

```powershell
python Harness/scripts/tools/harness_unreal_script.py --script Harness/scripts/unreal/verify_project.py --run
```

Record the exact map, commandlet, or generated JSON evidence in the task or cycle record. Keep one-off exploratory scripts out of permanent CI unless they become stable project checks.

### Tier 3: PIE Or Gameplay Evidence

Use this tier for UI, input, camera, replication, Blueprint-facing, or asset-heavy changes that automation cannot prove completely.

Acceptable evidence includes:

- Automation test output.
- A commandlet that loads the affected map and asserts required actors or assets.
- A short manual PIE note with the map, scenario, timestamp, worker, and result.
- A screenshot or generated report when visual behavior is the requested outcome.

## Template Boundary

Keep Tier 0 in the reusable template. Add Tier 1-3 jobs in the target project after engine paths and project automation are known. This keeps Harness portable while still making real projects accountable for Unreal-specific proof.
