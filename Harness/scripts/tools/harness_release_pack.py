"""Create or preview a clean Harness template zip package."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, rel


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
    "harness_release_pack.pyc",
    "handoff.md",
}


def should_include(path: Path, root: Path) -> bool:
    rel_path = path.relative_to(root)
    parts = set(rel_path.parts)
    if parts & EXCLUDED_PARTS:
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix == ".pyc":
        return False
    if (
        len(rel_path.parts) >= 3
        and rel_path.parts[0] == "Harness"
        and rel_path.parts[1:3] == ("work", "cycles")
        and path.suffix == ".md"
    ):
        return False
    if (
        len(rel_path.parts) >= 3
        and rel_path.parts[0] == "Harness"
        and rel_path.parts[1:3] == ("work", "tasks")
        and path.suffix == ".md"
        and path.name not in {"README.md", "task.example.md"}
    ):
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


def build_package(root: Path, output: Path, write: bool = False) -> dict:
    files = collect_files(root)
    output_path = output if output.is_absolute() else root / output
    report = {
        "root": str(root),
        "output": str(output_path),
        "write": write,
        "file_count": len(files),
        "files": [rel(path, root) for path in files],
        "ok": bool(files),
    }
    if not write:
        return report

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, rel(path, root))
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
    ]
    if report.get("bytes") is not None:
        lines.append(f"- Bytes: {report['bytes']}")
    lines.extend(["", "Included files:"])
    lines.extend(f"- {path}" for path in report["files"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or write a clean Harness template zip package.")
    parser.add_argument("--root", type=Path, default=None, help="Template root. Defaults to nearest Harness root.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Zip path. Relative paths are resolved from root.")
    parser.add_argument("--write", action="store_true", help="Actually write the zip package.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_package(root, args.output, write=args.write)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
