"""Check Python runtime availability for Harness tools."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, load_json, print_text_or_json


MIN_VERSION = (3, 10)


def run_version(command: list[str]) -> dict:
    executable = shutil.which(command[0]) if len(command) == 1 else shutil.which(command[0])
    if not executable:
        return {"command": " ".join(command), "found": False, "ok": False, "version": "", "path": ""}
    try:
        completed = subprocess.run(
            [*command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"command": " ".join(command), "found": True, "ok": False, "version": "", "path": executable, "error": str(exc)}
    output = (completed.stdout or completed.stderr).strip()
    version = parse_version(output)
    return {
        "command": " ".join(command),
        "found": True,
        "ok": completed.returncode == 0 and bool(version) and version >= MIN_VERSION,
        "version": ".".join(str(part) for part in version) if version else output,
        "path": executable,
        "returncode": completed.returncode,
    }


def current_python() -> dict:
    version = sys.version_info
    return {
        "command": "current",
        "found": True,
        "ok": (version.major, version.minor) >= MIN_VERSION,
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "path": sys.executable,
        "returncode": 0,
    }


def parse_version(text: str) -> tuple[int, int, int] | tuple[()]:
    parts = text.replace("Python", "").strip().split(".")
    if len(parts) < 2:
        return ()
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch_text = "".join(ch for ch in parts[2] if ch.isdigit()) if len(parts) > 2 else "0"
        return (major, minor, int(patch_text or "0"))
    except ValueError:
        return ()


def unreal_python_hint(root: Path) -> dict:
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    engine_root = (project.get("build", {}) if isinstance(project, dict) else {}).get("engine_root", "")
    if not engine_root:
        return {"configured": False, "candidates": []}
    base = Path(engine_root)
    candidates = [
        base / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "python.exe",
        base / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "pythonw.exe",
        base / "Engine" / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "python.exe",
        base / "Engine" / "Binaries" / "ThirdParty" / "Python3" / "Win64" / "pythonw.exe",
    ]
    return {
        "configured": True,
        "engine_root": engine_root,
        "candidates": [{"path": str(path), "exists": path.exists()} for path in candidates],
    }


def build_report(root: Path) -> dict:
    candidates = [
        current_python(),
        run_version(["python"]),
        run_version(["py", "-3"]),
        run_version(["python3"]),
    ]
    usable = [item for item in candidates if item["ok"]]
    return {
        "root": str(root),
        "minimum_version": ".".join(str(part) for part in MIN_VERSION),
        "ok": bool(usable),
        "usable_command": usable[0]["command"] if usable else "",
        "candidates": candidates,
        "unreal_python": unreal_python_hint(root),
        "install_hint": "Install Python 3.10+ manually from python.org or with: winget install Python.Python.3.12",
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Python Check",
        f"- Root: {report['root']}",
        f"- Minimum: Python {report['minimum_version']}+",
        f"- Status: {'ok' if report['ok'] else 'needs Python'}",
    ]
    if report["usable_command"]:
        lines.append(f"- Usable command: {report['usable_command']}")
    lines.append("")
    lines.append("Candidates:")
    for item in report["candidates"]:
        status = "ok" if item["ok"] else "unavailable"
        lines.append(f"- {item['command']}: {status} ({item.get('version') or item.get('path') or 'not found'})")
    unreal = report["unreal_python"]
    if unreal.get("configured"):
        lines.append("")
        lines.append("Unreal Python candidates:")
        lines.extend(f"- {item['path']}: {'exists' if item['exists'] else 'missing'}" for item in unreal["candidates"])
    if not report["ok"]:
        lines.append("")
        lines.append(report["install_hint"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Python 3 availability for Harness tools.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root)
    print_text_or_json(report if args.json else format_text(report), args.json)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
