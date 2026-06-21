"""Audit a target project before applying the single-layout Harness template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, load_json, rel


def files_under(path: Path) -> list[str]:
    if not path.exists():
        return []
    excluded = {".gitkeep", "README.md", "task.example.md"}
    return sorted(rel(item, path.parent) for item in path.rglob("*") if item.is_file() and item.name not in excluded)


def audit(root: Path) -> dict:
    harness = root / "Harness"
    split_dirs = [harness / name for name in ("Codex", "Claude", "Common")]
    has_split = any(path.exists() for path in split_dirs)
    has_single = all((harness / name).exists() for name in ("config", "scripts", "index", "work"))
    findings: list[dict] = []
    preserve: list[str] = []
    update: list[str] = []
    cleanup: list[str] = []
    template_controlled = [
        "run the new template's harness_update_plan.py before copying or replacing files",
        "review and merge AGENTS.md, CLAUDE.md, HARNESS.md, INSTALL.md, and Harness/README.md from the new template",
        "review and merge Harness/config/agents.json and Harness/config/cycle_policy.json",
        "review and merge standard Harness/scripts/ tools, build helpers, and Unreal helpers while preserving custom behavior",
        "review and merge Harness/work/tasks/task.example.md and template documentation examples",
        "run harness_knowledge.py after migration to reuse retained docs, indexes, task/cycle history, and archives",
    ]

    if not harness.exists():
        findings.append({"level": "error", "message": "Harness directory is missing"})
        layout = "missing"
    elif has_split:
        layout = "split_worker"
        findings.append({"level": "warning", "message": "split worker Harness layout detected"})
        for worker in ("Codex", "Claude"):
            base = harness / worker
            if base.exists():
                preserve.extend(
                    [
                        f"Harness/{worker}/config/",
                        f"Harness/{worker}/index/",
                        f"Harness/{worker}/work/",
                        f"Harness/{worker}/Progress.md",
                        f"Harness/{worker}/scripts/ custom changes",
                    ]
                )
        if (harness / "Common" / "docs").exists():
            preserve.append("Harness/Common/docs/")
        update.extend(
            [
                "merge worker config into Harness/config/ without overwriting project-specific values",
                "consolidate durable facts and unresolved work into Harness/work/state.md and Harness/work/next.md",
                "preserve conflicting or worker-specific history as separate Harness/work/tasks/ and Harness/work/cycles/ files",
                "merge worker indexes and custom scripts deliberately",
                "move Harness/Common/docs/ into Harness/docs/",
                *template_controlled,
            ]
        )
        cleanup.extend("Harness/" + name + "/ after the single Harness passes verification" for name in ("Codex", "Claude", "Common"))
    elif has_single:
        layout = "single"
        preserve.extend(
            [
                "Harness/config/project.json",
                "Harness/config/docs.json",
                "Harness/docs/",
                "Harness/index/",
                "Harness/work/",
                "Harness/Progress.md",
                "Harness/scripts/ custom changes",
            ]
        )
        update.extend(template_controlled)
    else:
        layout = "unknown"
        findings.append({"level": "warning", "message": "partial or older Harness layout detected; merge manually"})
        preserve.append("Harness/ contents until reviewed")
        update.extend(template_controlled)

    project_path = harness / "config" / "project.json"
    if has_split and not project_path.exists():
        for worker in ("Codex", "Claude"):
            candidate = harness / worker / "config" / "project.json"
            if candidate.exists():
                project_path = candidate
                break
    project = load_json(project_path, {}) or {}
    build = project.get("build", {}) if isinstance(project, dict) else {}
    if project_path.exists() and not project.get("template_mode", False) and not bool(build.get("engine_root") and build.get("editor_target_name")):
        findings.append({"level": "warning", "message": "project.json build config is incomplete"})

    task_files = files_under(harness / "work" / "tasks")
    cycle_files = files_under(harness / "work" / "cycles")
    return {
        "root": str(root),
        "ok": not any(item["level"] == "error" for item in findings),
        "layout": {"kind": layout, "has_harness": harness.exists(), "has_single": has_single, "has_split": has_split},
        "summary": {"task_files": len(task_files), "cycle_files": len(cycle_files), "findings": len(findings)},
        "project": {
            "exists": project_path.exists(),
            "path": rel(project_path, root),
            "project_name": project.get("project_name", "") if isinstance(project, dict) else "",
            "build_configured": bool(build.get("engine_root") and build.get("editor_target_name")),
        },
        "preserve": sorted(set(preserve)),
        "update": sorted(set(update)),
        "cleanup": sorted(set(cleanup)),
        "findings": findings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Migration Audit",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Layout: {report['layout']['kind']}",
    ]
    for section in ("preserve", "update", "cleanup"):
        lines.extend(["", section.capitalize() + ":"])
        lines.extend(f"- {item}" for item in report[section]) if report[section] else lines.append("- none")
    if report["findings"]:
        lines.extend(["", "Findings:"])
        lines.extend(f"- [{item['level']}] {item['message']}" for item in report["findings"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a project before migrating or updating Harness.")
    parser.add_argument("--target", type=Path, default=Path.cwd(), help="Target project root to audit.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    report = audit(args.target.resolve())
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
