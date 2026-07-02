"""Check whether Harness is connected to a real Unreal project after init/update."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel
from harness_scan import scan


PLACEHOLDER_MARKERS = (
    "TODO",
    "Fill `Harness/config/project.json`",
    "Record systems, maps, inputs",
    "Summarize the project purpose",
    "Add major systems",
    "List only important maps",
    "작성 필요",
)


def add_finding(findings: list[dict], level: str, path: str, message: str) -> None:
    findings.append({"level": level, "path": path, "message": message})


def _has_placeholder(path: Path) -> bool:
    text = read_text(path)
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _project_value(project: dict, key: str) -> str:
    value = project.get(key)
    return value.strip() if isinstance(value, str) else ""


def build_report(root: Path, after_update: bool = False) -> dict:
    harness = harness_dir(root)
    findings: list[dict] = []
    project_path = harness / "config" / "project.json"
    project = load_json(project_path, {}) or {}
    if not isinstance(project, dict):
        add_finding(findings, "error", "Harness/config/project.json", "project.json must be a JSON object")
        project = {}

    scan_report = scan(root, include_assets=False)
    uproject_files = [item["file"] for item in scan_report["uprojects"]]
    template_mode = bool(project.get("template_mode"))

    if template_mode:
        if uproject_files:
            add_finding(
                findings,
                "error",
                "Harness/config/project.json",
                "template_mode is still true even though this checkout contains a .uproject; set it to false after connecting Harness",
            )
        status = "template_mode" if not uproject_files else "template_mode_in_project"
    else:
        status = "project_connected"
        required_fields = [
            ("project_name", "project_name"),
            ("uproject_file", "uproject_file"),
            ("engine_version", "engine_version"),
            ("build.engine_root", "build.engine_root"),
            ("build.editor_target_name", "build.editor_target_name"),
        ]
        build = project.get("build", {}) if isinstance(project.get("build"), dict) else {}
        values = {
            "project_name": _project_value(project, "project_name"),
            "uproject_file": _project_value(project, "uproject_file"),
            "engine_version": _project_value(project, "engine_version"),
            "build.engine_root": build.get("engine_root", "").strip() if isinstance(build.get("engine_root"), str) else "",
            "build.editor_target_name": build.get("editor_target_name", "").strip() if isinstance(build.get("editor_target_name"), str) else "",
        }
        for field, label in required_fields:
            if not values[field]:
                add_finding(findings, "error", "Harness/config/project.json", f"missing required project connection field: {label}")

        uproject = values["uproject_file"]
        if uproject and not (root / uproject).is_file():
            add_finding(findings, "error", uproject, "configured uproject_file does not exist")
        if len(uproject_files) == 1 and uproject and uproject_files[0] != uproject:
            add_finding(findings, "warning", "Harness/config/project.json", f"configured uproject_file differs from discovered {uproject_files[0]}")
        if len(uproject_files) > 1 and not uproject:
            add_finding(findings, "error", "Harness/config/project.json", "multiple .uproject files found; set uproject_file explicitly")
        if not build.get("game_target_name"):
            add_finding(findings, "warning", "Harness/config/project.json", "build.game_target_name is blank; fill it when packaging or game-target builds matter")

        for relative in [
            "Harness/work/state.md",
            "Harness/work/next.md",
            "Harness/index/project_index.md",
        ]:
            path = root / relative
            if not path.exists():
                add_finding(findings, "error", relative, "required project connection file is missing")
            elif _has_placeholder(path):
                add_finding(findings, "error", relative, "still contains template placeholders; refresh it from actual Source, Config, assets, docs, logs, or verification output")

        verification_map = root / "Harness/index/verification_map.md"
        if verification_map.exists() and "Unreal Project CI Attachment" not in read_text(verification_map):
            add_finding(findings, "warning", "Harness/index/verification_map.md", "record the chosen Unreal verification tier after connection")

        if after_update:
            setup_doc = root / "Harness/docs/template/setup.md"
            if not setup_doc.exists():
                add_finding(findings, "warning", "Harness/docs/template/setup.md", "template setup guide is missing after update")

    errors = [item for item in findings if item["level"] == "error"]
    warnings = [item for item in findings if item["level"] == "warning"]
    return {
        "root": str(root),
        "ok": not errors,
        "status": status,
        "after_update": after_update,
        "template_mode": template_mode,
        "uprojects": uproject_files,
        "findings": findings,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "uproject_count": len(uproject_files),
            "modules": scan_report["source"]["modules"],
            "editor_targets": scan_report["source"]["editor_targets"],
            "game_targets": scan_report["source"]["game_targets"],
        },
        "guidance": [
            "Run harness_project_fill.py --write first when project.json fields are blank.",
            "Run harness_project_readiness.py after initialization or Harness update before declaring the project connected.",
            "Run harness_local_gate.py when the target Gitea project has no Actions or registered runners.",
        ],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Project Readiness",
        f"- Root: {report['root']}",
        f"- Status: {report['status']}",
        f"- Result: {'ok' if report['ok'] else 'needs attention'}",
        f"- UProject files: {', '.join(report['uprojects']) or 'none'}",
        f"- Errors: {report['summary']['errors']}",
        f"- Warnings: {report['summary']['warnings']}",
    ]
    if report["findings"]:
        lines.extend(["", "Findings:"])
        lines.extend(f"- [{item['level']}] {item['path']}: {item['message']}" for item in report["findings"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness project connection readiness after init or update.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--after-update", action="store_true", help="Also check post-update expectations.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, after_update=args.after_update)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
