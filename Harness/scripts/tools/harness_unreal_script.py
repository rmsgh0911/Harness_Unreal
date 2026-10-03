"""Inspect or run an Unreal Python script through UnrealEditor-Cmd."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, load_json, print_text_or_json, rel, require_valid_config


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
    root = root.resolve()
    require_valid_config(root)
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    build = project.get("build", {}) if isinstance(project, dict) else {}
    engine_root = build.get("engine_root", "")
    uproject_file = project.get("uproject_file", "") if isinstance(project, dict) else ""
    script_path = resolve_script_path(root, script)
    allowed_script_root = (root / UNREAL_SCRIPT_ROOT).resolve(strict=False)
    uproject_path = root / uproject_file if uproject_file else root / ""
    engine_path = Path(engine_root)
    if not engine_path.is_absolute():
        engine_path = root / engine_path
    editor_cmd = editor_cmd_path(str(engine_path.resolve())) if engine_root else Path("")
    command = []
    if engine_root and uproject_file:
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
    if engine_root and not editor_cmd.is_file():
        missing.append("UnrealEditor-Cmd.exe")
    if uproject_file and (not uproject_path.is_file() or uproject_path.suffix.casefold() != ".uproject"):
        missing.append(uproject_file)
    try:
        uproject_path.resolve().relative_to(root.resolve())
        allowed_script_root.relative_to(root.resolve())
        script_path.relative_to(allowed_script_root)
    except ValueError:
        missing.append("uproject must stay inside the project and script must stay under Harness/scripts/unreal")
    if script_path.suffix.lower() != ".py":
        missing.append("script must be a .py file")
    if not script_path.is_file():
        missing.append(script)
    if any(arg.split("=", 1)[0].casefold() in {"-run", "-script", "-executepythonscript", "-execcmds"} for arg in extra_args or []):
        missing.append("extra arguments cannot override the inspected script or commandlet")
    return {
        "root": str(root),
        "script": rel(script_path, root),
        "uproject": rel(uproject_path, root) if uproject_file else "",
        "editor_cmd": str(editor_cmd) if engine_root else "",
        "ok": not missing,
        "ready": not missing,
        "ran": False,
        "execution": "not_run",
        "acceptance": "not_evaluated",
        "missing": missing,
        "command": command,
    }


def run_report(root: Path, report: dict, *, json_output: bool = False) -> dict:
    result = dict(report)
    if not result["ready"]:
        result.update(ok=False, execution="blocked")
        return result
    try:
        completed = subprocess.run(result["command"], cwd=root, check=False,
                                   stdout=sys.stderr if json_output else None)
        result.update(ok=completed.returncode == 0, returncode=completed.returncode, ran=True,
                      execution="process_succeeded" if completed.returncode == 0 else "process_failed")
    except OSError as exc:
        result.update(ok=False, returncode=1, ran=False, execution="launch_failed", error=str(exc))
    return result


def format_text(report: dict) -> str:
    lines = [
        "Harness Unreal Script",
        f"- Root: {report['root']}",
        f"- Script: {report['script']}",
        f"- UProject: {report['uproject'] or 'not configured'}",
        f"- Readiness: {'ready' if report['ready'] else 'not ready'}",
        f"- Execution: {report['execution']}",
        "- Acceptance: not evaluated by process exit status",
    ]
    if "returncode" in report:
        lines.append(f"- Exit code: {report['returncode']}")
    if report.get("error"):
        lines.append(f"- Error: {report['error']}")
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
    try:
        report = build_report(root, script=args.script, extra_args=args.arg)
    except (OSError, ValueError) as exc:
        print_text_or_json({"ok": False, "error": str(exc), "ran": False}, True)
        raise SystemExit(1)
    if args.run:
        report = run_report(root, report, json_output=args.json)
    print_text_or_json(report if args.json else format_text(report), args.json)
    raise SystemExit(0 if report["ok"] else (report.get("returncode") or 1))


if __name__ == "__main__":
    main()
