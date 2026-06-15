"""Build a compact initialization or template-migration plan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, find_project_root, harness_dir, load_json, next_path, path_exists_text, print_text_or_json, rel, state_path


def build_plan(root: Path) -> dict:
    harness = harness_dir(root)
    project = load_json(harness / "config" / "project.json", {}) or {}
    docs = load_json(harness / "config" / "docs.json", {}) or {}
    uprojects = sorted(root.glob("*.uproject"))
    template_mode = bool(project.get("template_mode", False)) if isinstance(project, dict) else False
    project_configured = bool(project.get("project_name") and project.get("uproject_file")) if isinstance(project, dict) else False
    missing: list[str] = []
    preserve: list[str] = []
    fill: list[str] = []
    verify: list[str] = []

    required = [
        "HARNESS.md",
        "AGENTS.md",
        "Harness/README.md",
        "Harness/Codex/work/README.md",
        "Harness/Codex/work/state.md",
        "Harness/Codex/work/next.md",
        "Harness/Codex/index/README.md",
        "Harness/Codex/index/project_index.md",
        "Harness/Codex/config/project.json",
        "Harness/Codex/config/docs.json",
        "Harness/Codex/config/cycle_policy.json",
        "Harness/Codex/scripts/tools/tool_manifest.json",
    ]
    for item in required:
        if not (root / item).exists():
            missing.append(item)

    for item, path in [
        ("Harness/Codex/work/state.md", state_path(root)),
        ("Harness/Codex/work/next.md", next_path(root)),
        ("Harness/Codex/work/cycles/", cycles_dir(root)),
        ("Harness/Codex/config/project.json", harness / "config" / "project.json"),
    ]:
        if path.exists():
            preserve.append(item)

    if not project.get("project_name"):
        fill.append("Harness/Codex/config/project.json: project_name")
    if not project.get("uproject_file"):
        fill.append("Harness/Codex/config/project.json: uproject_file")
    build = project.get("build", {}) if isinstance(project, dict) else {}
    if not build.get("engine_root"):
        fill.append("Harness/Codex/config/project.json: build.engine_root")
    if not build.get("editor_target_name"):
        fill.append("Harness/Codex/config/project.json: build.editor_target_name")
    if not docs.get("doc_roots"):
        fill.append("Harness/Codex/config/docs.json: doc_roots")
    common_docs = root / "Harness" / "Common" / "docs"
    if not (common_docs / "README.md").exists():
        fill.append("Harness/Common/docs/README.md")

    verify.extend(
        [
            "python Harness/Codex/scripts/tools/harness_python_check.py",
            "python Harness/Codex/scripts/tools/harness_docs_check.py --json",
            "python Harness/Codex/scripts/tools/harness_doctor.py",
            "python Harness/Codex/scripts/tools/harness_scan.py --json",
        ]
    )
    if project.get("uproject_file") or len(uprojects) == 1:
        verify.append("python Harness/Codex/scripts/unreal/verify_project.py via UnrealEditor-Cmd")

    return {
        "root": str(root),
        "mode_hint": mode_hint(
            has_harness=harness.exists(),
            has_uproject=bool(uprojects),
            project_configured=project_configured,
            template_mode=template_mode,
        ),
        "template_mode": template_mode,
        "uprojects": [rel(path, root) for path in uprojects],
        "status": {
            "HARNESS.md": path_exists_text(root / "HARNESS.md"),
            "Harness/": path_exists_text(harness),
            "Harness/Common/docs/": path_exists_text(common_docs),
        },
        "missing_template_files": missing,
        "preserve": preserve,
        "fill": fill,
        "verify": verify,
        "ok": not missing,
    }


def mode_hint(has_harness: bool, has_uproject: bool, project_configured: bool, template_mode: bool = False) -> str:
    if has_harness and template_mode and not has_uproject:
        return "template_ready"
    if has_harness and template_mode and has_uproject:
        return "turn_off_template_mode_and_fill_project"
    if has_harness and not has_uproject and not project_configured:
        return "template_ready"
    if not has_harness:
        return "initialize"
    if not project_configured:
        return "initialize_or_fill_project"
    return "migrate_or_update"


def format_text(plan: dict) -> str:
    lines = [
        "Harness Init Plan",
        f"- Root: {plan['root']}",
        f"- Mode hint: {plan['mode_hint']}",
        f"- UProject files: {', '.join(plan['uprojects']) or 'none found'}",
        f"- Status: {'ok' if plan['ok'] else 'missing template files'}",
    ]
    for section, title in [("missing_template_files", "Missing"), ("preserve", "Preserve"), ("fill", "Fill"), ("verify", "Verify")]:
        lines.extend(["", f"{title}:"])
        items = plan[section]
        lines.extend(f"- {item}" for item in items) if items else lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a short Harness initialization or migration plan.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    plan = build_plan(root)
    print_text_or_json(plan if args.json else format_text(plan), args.json)
    raise SystemExit(0 if plan["ok"] else 1)


if __name__ == "__main__":
    main()
