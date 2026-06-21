"""Create or preview a clean Harness template zip package."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, rel
from harness_release_check import build_report as build_release_report


DEFAULT_OUTPUT = Path("dist") / "Harness_Unreal_Template.zip"
ROOT_FILES = [
    "README.md",
    "INSTALL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "HARNESS.md",
    ".gitattributes",
    ".gitignore",
]
EXCLUDED_PARTS = {
    ".git",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    "Binaries",
    "Intermediate",
    "Saved",
    "DerivedDataCache",
    "dist",
}
EXCLUDED_NAMES = {
    "handoff.md",
}


def should_include(path: Path, root: Path) -> bool:
    rel_path = path.relative_to(root)
    relative = rel_path.as_posix()
    parts = set(rel_path.parts)
    if path.is_symlink():
        return False
    if parts & EXCLUDED_PARTS:
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix == ".pyc":
        return False
    if len(rel_path.parts) >= 3 and rel_path.parts[:3] == ("Harness", "work", "cycles") and relative != "Harness/work/cycles/.gitkeep":
        return False
    if len(rel_path.parts) >= 3 and rel_path.parts[:3] == ("Harness", "work", "tasks") and relative not in {
        "Harness/work/tasks/README.md",
        "Harness/work/tasks/task.example.md",
    }:
        return False
    if len(rel_path.parts) >= 3 and rel_path.parts[:3] == ("Harness", "work", "archive") and relative != "Harness/work/archive/README.md":
        return False
    return True


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for item in ROOT_FILES:
        path = root / item
        if path.is_file() and should_include(path, root):
            files.append(path)

    harness = root / "Harness"
    if harness.exists():
        for path in sorted(harness.rglob("*")):
            if path.is_file() and should_include(path, root):
                files.append(path)

    return sorted(dict.fromkeys(files))


def build_package(root: Path, output: Path, write: bool = False, force: bool = False) -> dict:
    files = collect_files(root)
    output_path = (output if output.is_absolute() else root / output).resolve()
    release_check = build_release_report(root, strict=True)
    output_errors: list[str] = []
    if output_path.suffix.casefold() != ".zip":
        output_errors.append("output_must_use_zip_extension")
    if output_path in {path.resolve() for path in files}:
        output_errors.append("output_would_overwrite_packaged_source")
    try:
        output_path.relative_to((root / "Harness").resolve())
        output_errors.append("output_must_be_outside_harness_tree")
    except ValueError:
        pass
    report = {
        "root": str(root),
        "output": str(output_path),
        "write": write,
        "file_count": len(files),
        "files": [rel(path, root) for path in files],
        "ok": bool(files) and not output_errors and (release_check["ok"] or force),
        "forced": force,
        "output_errors": output_errors,
        "release_check": {
            "ok": release_check["ok"],
            "errors": release_check["errors"],
            "warnings": release_check["warnings"],
        },
    }
    if not write or not report["ok"]:
        report["blocked"] = bool(write and not report["ok"])
        return report

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(prefix=f".{output_path.stem}-", suffix=".tmp", dir=output_path.parent)
    os.close(temporary_fd)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, rel(path, root))
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    report["bytes"] = output_path.stat().st_size
    return report


def format_text(report: dict) -> str:
    lines = [
        "Harness Release Pack",
        f"- Root: {report['root']}",
        f"- Output: {report['output']}",
        f"- Mode: {'write' if report['write'] else 'dry-run'}",
        f"- Files: {report['file_count']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Strict release check: {'ok' if report['release_check']['ok'] else 'failed'}",
    ]
    if report.get("bytes") is not None:
        lines.append(f"- Bytes: {report['bytes']}")
    if report["output_errors"]:
        lines.extend(f"- Output error: {error}" for error in report["output_errors"])
    lines.extend(["", "Included files:"])
    lines.extend(f"- {path}" for path in report["files"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or write a clean Harness template zip package.")
    parser.add_argument("--root", type=Path, default=None, help="Template root. Defaults to nearest Harness root.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Zip path. Relative paths are resolved from root.")
    parser.add_argument("--write", action="store_true", help="Actually write the zip package.")
    parser.add_argument("--force", action="store_true", help="Write even when strict release hygiene fails. Use only for exceptional diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_package(root, args.output, write=args.write, force=args.force)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
