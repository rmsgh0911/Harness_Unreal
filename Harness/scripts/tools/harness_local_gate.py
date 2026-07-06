"""Run the local finish gate for projects without server-side CI."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, rel
from harness_memory_review import build_review as build_memory_review


def clean_python_caches(root: Path) -> dict:
    harness = harness_dir(root)
    removed: list[str] = []
    errors: list[dict] = []

    for path in sorted(harness.rglob("__pycache__")):
        try:
            shutil.rmtree(path)
            removed.append(rel(path, root))
        except OSError as exc:
            errors.append({"path": rel(path, root), "error": str(exc)})

    for path in sorted(harness.rglob("*.pyc")):
        try:
            path.unlink()
            removed.append(rel(path, root))
        except OSError as exc:
            errors.append({"path": rel(path, root), "error": str(exc)})

    return {
        "ok": not errors,
        "removed": removed,
        "errors": errors,
    }


def run_command(root: Path, command: list[str]) -> dict:
    # A finish gate must fail with a clear step, not a traceback, when a
    # required executable (for example git) is missing from PATH.
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return {
            "ok": False,
            "returncode": -1,
            "command": " ".join(command),
            "output": f"command could not start: {exc}",
        }
    output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": " ".join(command),
        "output": output,
    }


def build_gate(root: Path, release: bool = False, skip_tests: bool = False) -> dict:
    steps: list[dict] = []
    tests_dir = harness_dir(root) / "scripts" / "tools" / "tests"

    if skip_tests:
        steps.append({"name": "tool_tests", "ok": True, "skipped": True, "command": "skipped"})
    elif tests_dir.exists():
        steps.append({
            "name": "tool_tests",
            **run_command(root, [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests_dir), "-p", "test_*.py"]),
        })
    else:
        steps.append({"name": "tool_tests", "ok": True, "skipped": True, "command": "tests_not_present"})

    cleanup = clean_python_caches(root)
    steps.append({"name": "clean_python_caches", **cleanup})

    verify_command = [
        sys.executable,
        str(harness_dir(root) / "scripts" / "tools" / "harness_verify_all.py"),
        "--skip-tool-tests",
    ]
    steps.append({"name": "harness_verify_all", **run_command(root, verify_command)})

    if release:
        release_command = [
            sys.executable,
            str(harness_dir(root) / "scripts" / "tools" / "harness_release_check.py"),
            "--strict",
        ]
        steps.append({"name": "strict_release_check", **run_command(root, release_command)})

    steps.append({"name": "memory_review", **build_memory_review(root)})
    steps.append({"name": "diff_check", **run_command(root, ["git", "diff", "--check"])})
    steps.append({"name": "diff_stat", **run_command(root, ["git", "diff", "--stat"])})

    return {
        "root": str(root),
        "ok": all(step.get("ok") is True for step in steps),
        "mode": "release" if release else "project",
        "steps": steps,
        "guidance": "Use this when GitHub/Gitea Actions or runners are unavailable; record skipped Unreal build, commandlet, or PIE evidence separately.",
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Local Gate",
        f"- Root: {report['root']}",
        f"- Mode: {report['mode']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
    ]
    for step in report["steps"]:
        status = "ok" if step.get("ok") else "failed"
        if step.get("skipped"):
            status = "skipped"
        if step["name"] == "memory_review" and step.get("ok") and step.get("review_recommended"):
            status = "review recommended"
        lines.append(f"- {step['name']}: {status}")
    memory_steps = [step for step in report["steps"] if step["name"] == "memory_review" and step.get("review_recommended")]
    if memory_steps:
        lines.append("")
        lines.append("Memory review:")
        for item in memory_steps[0].get("suggestions", [])[:5]:
            lines.append(f"- {item['candidate']}: {item['reason']} ({item['example_path']})")
        lines.append("- Add only compact reviewed entries; skip command logs, temporary state, long output, credentials, and unverified guesses.")
    failed = [step for step in report["steps"] if not step.get("ok")]
    if failed:
        lines.append("")
        lines.append("Failed output:")
        for step in failed:
            lines.append(f"## {step['name']}")
            if step.get("command"):
                lines.append(f"$ {step['command']}")
            if step.get("output"):
                lines.append(step["output"])
            if step.get("errors"):
                lines.extend(f"- {item['path']}: {item['error']}" for item in step["errors"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local finish gate when CI is unavailable.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--release", action="store_true", help="Add strict template release hygiene check.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip tool tests when they already ran locally.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_gate(root, release=args.release, skip_tests=args.skip_tests)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
