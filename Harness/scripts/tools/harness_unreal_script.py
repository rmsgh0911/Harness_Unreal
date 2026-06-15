"""Inspect or run an Unreal Python script through UnrealEditor-Cmd."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, load_json, print_text_or_json, rel


DEFAULT_SCRIPT = "Harness/scripts/unreal/verify_project.py"
UNREAL_SCRIPT_ROOT = Path("Harness/scripts/unreal")


def editor_cmd_path(engine_root: str) -> Path:
    base = Path(engine_root)
    candidates = [
        base / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
        base / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_script_path(root: Path, script: str) -> Path:
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = root / script_path
    return script_path.resolve(strict=False)


def build_report(root: Path, script: str = DEFAULT_SCRIPT, extra_args: list[str] | None = None) -> dict:
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    build = project.get("build", {}) if isinstance(project, dict) else {}
    engine_root = build.get("engine_root", "")
    uproject_file = project.get("uproject_file", "") if isinstance(project, dict) else ""
    script_path = resolve_script_path(root, script)
    allowed_script_root = (root / UNREAL_SCRIPT_ROOT).resolve(strict=False)
    uproject_path = root / uproject_file if uproject_file else root / ""
    editor_cmd = editor_cmd_path(engine_root) if engine_root else Path("")
    command = []
    if editor_cmd and uproject_file:
        command = [
            str(editor_cmd),
            str(uproject_path),
            "-run=pythonscript",
            f"-script={script_path}",
            "-unattended",
            "-nop4",
            "-nosplash",
            *(extra_args or []),
        ]
    missing = []
    if not engine_root:
        missing.append("build.engine_root")
    if not uproject_file:
        missing.append("uproject_file")
    if engine_root and not editor_cmd.exists():
        missing.append("UnrealEditor-Cmd.exe")
    if uproject_file and not uproject_path.exists():
        missing.append(uproject_file)
    try:
        script_path.relative_to(allowed_script_root)
    except ValueError:
        missing.append("script must stay under Harness/scripts/unreal")
    if script_path.suffix.lower() != ".py":
        missing.append("script must be a .py file")
    if not script_path.exists():
        missing.append(script)
    return {
        "root": str(root),
        "script": rel(script_path, root),
        "uproject": rel(uproject_path, root) if uproject_file else "",
        "editor_cmd": str(editor_cmd) if engine_root else "",
        "ok": not missing,
        "missing": missing,
        "command": command,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Unreal Script",
        f"- Root: {report['root']}",
        f"- Script: {report['script']}",
        f"- UProject: {report['uproject'] or 'not configured'}",
        f"- Status: {'ready' if report['ok'] else 'not ready'}",
    ]
    if report["missing"]:
        lines.append("")
        lines.append("Missing:")
        lines.extend(f"- {item}" for item in report["missing"])
    if report["command"]:
        lines.append("")
        lines.append("Command:")
        lines.append(" ".join(f'"{item}"' if " " in item else item for item in report["command"]))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or run an Unreal Python script through UnrealEditor-Cmd.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--script", default=DEFAULT_SCRIPT, help=f"Script path relative to root. Defaults to {DEFAULT_SCRIPT}.")
    parser.add_argument("--arg", action="append", default=[], help="Extra argument passed to UnrealEditor-Cmd. Repeatable.")
    parser.add_argument("--run", action="store_true", help="Run the command. Without this, only prints readiness and command.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, script=args.script, extra_args=args.arg)
    if args.run:
        if not report["ok"]:
            print_text_or_json(report if args.json else format_text(report), args.json)
            raise SystemExit(1)
        completed = subprocess.run(report["command"], cwd=root, check=False)
        report["returncode"] = completed.returncode
        report["ran"] = True
        print_text_or_json(report if args.json else format_text(report), args.json)
        raise SystemExit(completed.returncode)
    report["ran"] = False
    print_text_or_json(report if args.json else format_text(report), args.json)


if __name__ == "__main__":
    main()
