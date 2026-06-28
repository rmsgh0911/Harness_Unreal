"""Check field-proven Harness operating risks without modifying files."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel


REF_HEADS_PREFIX = "refs/heads/"
SUSPICIOUS_TEXT_ARTIFACT_PATTERN = re.compile(r"\ufffd|(?<=\S)\?\?(?=\S)")


def _branch_name_from_ref(ref: str) -> str:
    if ref.startswith(REF_HEADS_PREFIX):
        return ref[len(REF_HEADS_PREFIX):]
    return ref


def _run_git(root: Path, args: list[str]) -> dict:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _contains_unreal_import(path: Path) -> bool:
    text = read_text(path)
    return any(
        line.strip() == "import unreal"
        or line.strip().startswith("import unreal ")
        or line.strip().startswith("from unreal ")
        for line in text.splitlines()
    )


def _field_guide_report(root: Path) -> dict:
    guide = harness_dir(root) / "docs" / "AgentFieldGuide.md"
    references = [
        "HARNESS.md",
        "README.md",
        "INSTALL.md",
        "Harness/README.md",
        "Harness/docs/README.md",
        "Harness/scripts/tools/README.md",
    ]
    linked_from = [
        path
        for path in references
        if "AgentFieldGuide.md" in read_text(root / path)
    ]
    return {
        "exists": guide.exists(),
        "path": rel(guide, root),
        "linked_from": linked_from,
        "linked": bool(linked_from),
    }


def _project_root_report(root: Path, template_mode: bool) -> dict:
    uprojects = sorted(path for path in root.glob("*.uproject") if path.is_file())
    source_exists = (root / "Source").is_dir()
    plugins_exists = (root / "Plugins").is_dir()
    nested_template_roots = sorted(
        path for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and (path / "HARNESS.md").is_file()
        and (path / "Harness").is_dir()
    )
    return {
        "template_mode": template_mode,
        "uprojects": [rel(path, root) for path in uprojects],
        "source_exists": source_exists,
        "plugins_exists": plugins_exists,
        "nested_template_roots": [rel(path, root) for path in nested_template_roots],
        "looks_like_template_only": not uprojects and not source_exists and not plugins_exists,
    }


def _text_artifact_report(root: Path) -> list[dict]:
    checked_paths = [
        root / "HARNESS.md",
        harness_dir(root) / "docs" / "AgentFieldGuide.md",
        harness_dir(root) / "README.md",
        harness_dir(root) / "docs" / "README.md",
    ]
    findings = []
    for path in checked_paths:
        text = read_text(path)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if SUSPICIOUS_TEXT_ARTIFACT_PATTERN.search(line):
                findings.append({
                    "path": rel(path, root),
                    "line": line_number,
                    "message": "suspicious_text_encoding_artifact",
                })
    return findings


def _unreal_script_report(root: Path) -> dict:
    script_root = harness_dir(root) / "scripts" / "unreal"
    scripts = []
    if script_root.exists():
        for path in sorted(script_root.glob("*.py")):
            imports_unreal = _contains_unreal_import(path)
            scripts.append({
                "path": rel(path, root),
                "imports_unreal": imports_unreal,
                "run_with": f"python Harness/scripts/tools/harness_unreal_script.py --script {rel(path, root)} --run"
                if imports_unreal else "python",
            })
    return {
        "script_dir_exists": script_root.exists(),
        "scripts": scripts,
        "unreal_import_count": sum(1 for item in scripts if item["imports_unreal"]),
    }


def _worktree_report(root: Path, branches: list[str]) -> dict:
    report = {
        "git_available": False,
        "worktrees": [],
        "status": None,
        "remote_refs": [],
        "remote_check_requested": branches,
        "remote_check_enabled": bool(branches),
        "remote_alignment": {
            "enabled": bool(branches),
            "requested": branches,
            "found": [],
            "missing": [],
            "commits": [],
            "aligned": None,
        },
    }
    status = _run_git(root, ["status", "--short", "--branch"])
    if not status["ok"]:
        report["status_error"] = status["stderr"] or status["stdout"]
        return report

    report["git_available"] = True
    report["status"] = status["stdout"]

    worktree = _run_git(root, ["worktree", "list", "--porcelain"])
    if worktree["ok"]:
        current: dict[str, str] = {}
        for line in worktree["stdout"].splitlines():
            if not line.strip():
                if current:
                    report["worktrees"].append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            current[key] = value
        if current:
            report["worktrees"].append(current)
    else:
        report["worktree_error"] = worktree["stderr"] or worktree["stdout"]

    checkout_count = len(report["worktrees"])
    report["checkout_count"] = checkout_count
    report["checkout_mode"] = "parallel_worktrees" if checkout_count > 1 else "single_checkout"

    if branches:
        remote = _run_git(root, ["ls-remote", "--heads", "origin", *branches])
        report["remote_ok"] = remote["ok"]
        if remote["ok"]:
            for line in remote["stdout"].splitlines():
                commit, _, ref = line.partition("\t")
                if ref:
                    report["remote_refs"].append({"ref": ref, "commit": commit})
            found = sorted(_branch_name_from_ref(item["ref"]) for item in report["remote_refs"])
            commits = sorted({item["commit"] for item in report["remote_refs"]})
            report["remote_alignment"] = {
                "enabled": True,
                "requested": branches,
                "found": found,
                "missing": sorted(set(branches) - set(found)),
                "commits": commits,
                "aligned": bool(branches) and len(commits) == 1 and set(found) == set(branches),
            }
        else:
            report["remote_error"] = remote["stderr"] or remote["stdout"]
            report["remote_alignment"]["aligned"] = False
    return report


def build_report(root: Path, branches: list[str] | None = None) -> dict:
    branches = branches or []
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    template_mode = bool(project.get("template_mode")) if isinstance(project, dict) else False

    guide = _field_guide_report(root)
    project_root = _project_root_report(root, template_mode)
    text_artifacts = _text_artifact_report(root)
    unreal_scripts = _unreal_script_report(root)
    worktrees = _worktree_report(root, branches)

    errors: list[dict] = []
    warnings: list[dict] = []
    notes: list[dict] = []

    if not guide["exists"]:
        errors.append({"path": guide["path"], "message": "field_guide_missing"})
    elif not guide["linked"]:
        warnings.append({"path": guide["path"], "message": "field_guide_not_linked_from_main_docs"})

    if not template_mode and project_root["looks_like_template_only"]:
        warnings.append({
            "path": ".",
            "message": "real_project_mode_but_no_uproject_source_or_plugins_found; verify actual project root",
        })
    if template_mode and project_root["uprojects"]:
        warnings.append({"path": ".", "message": "template_mode_contains_uproject_files"})
    for nested_root in project_root["nested_template_roots"]:
        warnings.append({
            "path": nested_root,
            "message": "nested_harness_root_detected; verify this is an intentional review copy",
        })
    for finding in text_artifacts:
        warnings.append(finding)

    for item in unreal_scripts["scripts"]:
        if item["imports_unreal"]:
            notes.append({
                "path": item["path"],
                "message": "imports_unreal; use harness_unreal_script wrapper",
                "command": item["run_with"],
            })

    if branches:
        alignment = worktrees.get("remote_alignment", {})
        missing = alignment.get("missing", [])
        if missing:
            warnings.append({"path": "origin", "message": "remote_branches_missing:" + ",".join(missing)})
        commits = alignment.get("commits", [])
        if alignment.get("aligned") and commits:
            notes.append({"path": "origin", "message": "requested_remote_refs_aligned", "commit": commits[0]})
        elif len(commits) > 1:
            warnings.append({"path": "origin", "message": "requested_remote_refs_diverged"})

    return {
        "root": str(root),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
        "field_guide": guide,
        "project_root": project_root,
        "text_artifacts": text_artifacts,
        "unreal_scripts": unreal_scripts,
        "worktrees": worktrees,
    }


def format_text(report: dict) -> str:
    worktree_report = report["worktrees"]
    if worktree_report.get("git_available"):
        checkout_text = f"{worktree_report.get('checkout_count', 0)} ({worktree_report.get('checkout_mode', 'unknown')})"
    else:
        checkout_text = "unavailable"
    lines = [
        "Harness Field Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Field guide: {'ok' if report['field_guide']['exists'] else 'missing'}",
        f"- Project root: {'template_mode' if report['project_root']['template_mode'] else 'project_mode'}",
        f"- Unreal scripts importing unreal: {report['unreal_scripts']['unreal_import_count']}",
        f"- Git checkouts/worktrees: {checkout_text}",
    ]
    if report["errors"]:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["errors"])
    if report["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item['path']}: {item['message']}" for item in report["warnings"])
    if report["notes"]:
        lines.append("")
        lines.append("Notes:")
        for item in report["notes"]:
            suffix = f" ({item['command']})" if "command" in item else ""
            if "commit" in item:
                suffix = f" ({item['commit']})"
            lines.append(f"- {item['path']}: {item['message']}{suffix}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check field-proven Harness operating risks.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--branches", nargs="*", default=[], help="Optional branch names to compare with origin refs. Omit for single-checkout projects or when no branch-family sync is requested.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, branches=args.branches)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
