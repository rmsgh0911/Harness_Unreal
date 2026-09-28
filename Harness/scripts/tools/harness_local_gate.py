"""Run the local finish gate for projects without server-side CI."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir
from harness_memory_review import build_review as build_memory_review


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def inspect_python_caches(root: Path) -> dict:
    harness = harness_dir(root)
    cache_dirs: list[Path] = []
    pyc_files: list[Path] = []
    blocked_links: list[Path] = []

    if harness.exists():
        for current, dir_names, file_names in os.walk(harness, topdown=True, followlinks=False):
            current_path = Path(current)
            retained_dirs: list[str] = []
            for name in dir_names:
                path = current_path / name
                if current_path == harness and name == ".runtime":
                    continue
                if _is_link_or_junction(path) or not _is_within(path, harness):
                    blocked_links.append(path)
                elif name == "__pycache__":
                    cache_dirs.append(path)
                else:
                    retained_dirs.append(name)
            dir_names[:] = retained_dirs
            for name in file_names:
                if not name.endswith(".pyc"):
                    continue
                path = current_path / name
                if _is_link_or_junction(path) or not _is_within(path, harness):
                    blocked_links.append(path)
                else:
                    pyc_files.append(path)

    found = [*cache_dirs, *pyc_files]
    return {
        "ok": True,
        "scope": "Harness/",
        "executed": True,
        "found": [_display_path(path, root) for path in found],
        "found_count": len(found),
        "cache_dirs": [_display_path(path, root) for path in cache_dirs],
        "pyc_files": [_display_path(path, root) for path in pyc_files],
        "blocked_links": [_display_path(path, root) for path in blocked_links],
    }


def _validate_cache_target(path: Path, harness: Path, kind: str) -> str | None:
    if _is_link_or_junction(path):
        return "cleanup refused for a symlink or junction"
    if not _is_within(path, harness):
        return "cleanup target escapes the Harness root"
    if kind == "directory" and path.name != "__pycache__":
        return "cleanup directory is not named __pycache__"
    if kind == "file" and path.suffix != ".pyc":
        return "cleanup file is not a .pyc file"
    return None


def clean_python_caches(root: Path) -> dict:
    harness = harness_dir(root)
    inventory = inspect_python_caches(root)
    removed: list[str] = []
    errors: list[dict] = [
        {"path": path, "error": "cleanup refused because the path is a symlink, junction, or escapes Harness/"}
        for path in inventory["blocked_links"]
    ]

    def retry_writable(function, raw_path: str, _error) -> None:
        target = Path(raw_path)
        if _is_link_or_junction(target) or not _is_within(target, harness):
            raise PermissionError(f"cleanup retry refused outside Harness/: {target}")
        os.chmod(target, stat.S_IWRITE)
        function(raw_path)

    for relative in inventory["cache_dirs"]:
        path = root / relative
        refusal = _validate_cache_target(path, harness, "directory")
        if refusal:
            errors.append({"path": relative, "error": refusal})
            continue
        try:
            shutil.rmtree(path, onerror=retry_writable)
            removed.append(relative)
        except OSError as exc:
            errors.append({"path": relative, "error": str(exc)})

    for relative in inventory["pyc_files"]:
        path = root / relative
        refusal = _validate_cache_target(path, harness, "file")
        if refusal:
            errors.append({"path": relative, "error": refusal})
            continue
        try:
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    refusal = _validate_cache_target(path, harness, "file")
                    if refusal:
                        raise PermissionError(refusal)
                    path.chmod(stat.S_IWRITE)
                    path.unlink()
                removed.append(relative)
        except OSError as exc:
            errors.append({"path": relative, "error": str(exc)})

    return {
        "ok": not errors,
        "scope": "Harness/",
        "executed": True,
        "found": inventory["found"],
        "found_count": inventory["found_count"],
        "blocked_links": inventory["blocked_links"],
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
            "executed": False,
            "returncode": -1,
            "command": " ".join(command),
            "output": f"command could not start: {exc}",
        }
    output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    return {
        "ok": completed.returncode == 0,
        "executed": True,
        "returncode": completed.returncode,
        "command": " ".join(command),
        "output": output,
    }


def _skipped_command_step(name: str, command: list[str], scope: str, reason: str) -> dict:
    return {
        "name": name,
        "ok": True,
        "executed": False,
        "skipped": True,
        "scope": scope,
        "command": " ".join(command),
        "output": reason,
    }


def _status_entries(output: str) -> list[str]:
    return [entry for entry in output.split("\0") if entry]


def build_git_steps(root: Path) -> list[dict]:
    repository = {
        "name": "git_repository",
        "scope": "repository",
        **run_command(root, ["git", "rev-parse", "--show-toplevel"]),
    }
    steps = [repository]
    commands = [
        ("git_status", ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], "working_tree"),
        ("conflict_check", ["git", "ls-files", "-u", "-z"], "index"),
        ("diff_check", ["git", "diff", "--check"], "unstaged"),
        ("staged_diff_check", ["git", "diff", "--cached", "--check"], "staged"),
        ("diff_stat", ["git", "diff", "--stat"], "unstaged"),
        ("staged_diff_stat", ["git", "diff", "--cached", "--stat"], "staged"),
    ]
    if not repository["ok"]:
        steps.extend(_skipped_command_step(name, command, scope, "git repository check failed") for name, command, scope in commands)
        return steps

    try:
        git_root = Path(repository["output"]).resolve()
    except OSError:
        git_root = Path()
    if git_root != root.resolve():
        repository["ok"] = False
        repository["output"] = f"git top-level does not match the Harness project root: {git_root}"
        steps.extend(_skipped_command_step(name, command, scope, "git repository root mismatch") for name, command, scope in commands)
        return steps

    status = {"name": "git_status", "scope": "working_tree", **run_command(root, commands[0][1])}
    entries = _status_entries(status["output"]) if status["ok"] else []
    status["entries"] = entries
    status["untracked"] = [entry[3:] for entry in entries if entry.startswith("?? ")]
    status["untracked_count"] = len(status["untracked"])
    status["output"] = "\n".join(entries)
    steps.append(status)

    conflicts = {"name": "conflict_check", "scope": "index", **run_command(root, commands[1][1])}
    conflict_entries = _status_entries(conflicts["output"]) if conflicts["executed"] else []
    conflict_paths = sorted({entry.split("\t", 1)[-1] for entry in conflict_entries if "\t" in entry})
    conflicts["conflicts"] = conflict_paths
    conflicts["conflict_count"] = len(conflict_paths)
    conflicts["output"] = "\n".join(conflict_paths)
    if conflict_paths:
        conflicts["ok"] = False
    steps.append(conflicts)

    for name, command, scope in commands[2:]:
        steps.append({"name": name, "scope": scope, **run_command(root, command)})
    return steps


def build_gate(root: Path, release: bool = False, skip_tests: bool = False, cleanup_caches: bool = False) -> dict:
    steps: list[dict] = []
    tests_dir = harness_dir(root) / "scripts" / "tools" / "tests"

    if skip_tests:
        steps.append({"name": "tool_tests", "ok": True, "executed": False, "skipped": True, "scope": "Harness tool tests", "command": "skipped"})
    elif tests_dir.exists():
        steps.append({
            "name": "tool_tests",
            "scope": "Harness tool tests",
            **run_command(root, [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests_dir), "-p", "test_*.py"]),
        })
    else:
        steps.append({"name": "tool_tests", "ok": True, "executed": False, "skipped": True, "scope": "Harness tool tests", "command": "tests_not_present"})

    if cleanup_caches:
        steps.append({"name": "clean_python_caches", **clean_python_caches(root)})
    else:
        inventory = inspect_python_caches(root)
        steps.append({
            "name": "clean_python_caches",
            **inventory,
            "executed": False,
            "skipped": True,
            "removed": [],
            "errors": [],
            "command": "pass --cleanup-caches to remove reported cache entries",
        })

    verify_command = [
        sys.executable,
        str(harness_dir(root) / "scripts" / "tools" / "harness_verify_all.py"),
        "--skip-tool-tests",
    ]
    steps.append({"name": "harness_verify_all", "scope": "Harness verification", **run_command(root, verify_command)})

    if release:
        release_command = [
            sys.executable,
            str(harness_dir(root) / "scripts" / "tools" / "harness_release_check.py"),
            "--strict",
        ]
        steps.append({"name": "strict_release_check", "scope": "template release", **run_command(root, release_command)})

    steps.append({"name": "memory_review", "scope": "changed paths and reviewed memory", "executed": True, **build_memory_review(root)})
    steps.extend(build_git_steps(root))
    for step in steps:
        step.setdefault("scope", "unspecified")
        step.setdefault("executed", False)
        step.setdefault("skipped", False)

    return {
        "root": str(root),
        "ok": all(step.get("ok") is True for step in steps),
        "mode": "release" if release else "project",
        "cache_cleanup_requested": cleanup_caches,
        "steps": steps,
        "guidance": "Use this when GitHub/Gitea Actions or runners are unavailable. The default gate is read-only; cache deletion requires --cleanup-caches. Record skipped Unreal build, commandlet, or PIE evidence separately.",
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
    cache_steps = [step for step in report["steps"] if step["name"] == "clean_python_caches"]
    if cache_steps and cache_steps[0].get("found_count"):
        cache_step = cache_steps[0]
        action = f"removed {len(cache_step.get('removed', []))}" if cache_step.get("executed") else "not removed (pass --cleanup-caches to clean)"
        lines.append(f"- Python cache entries: {cache_step['found_count']}; {action}")
    status_steps = [step for step in report["steps"] if step["name"] == "git_status"]
    if status_steps and status_steps[0].get("untracked"):
        lines.extend(["", "Untracked files:", *(f"- {path}" for path in status_steps[0]["untracked"][:40])])
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
    parser.add_argument("--cleanup-caches", action="store_true", help="Explicitly remove Python caches under Harness/ after a containment check.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_gate(root, release=args.release, skip_tests=args.skip_tests, cleanup_caches=args.cleanup_caches)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
