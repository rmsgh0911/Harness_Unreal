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
from harness_template_manifest import MANIFEST_RELATIVE, discover_release_files, release_files_from_manifest, should_include


DEFAULT_OUTPUT = Path("dist") / "Harness_Unreal_Template.zip"
DETERMINISTIC_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def collect_files(root: Path) -> list[Path]:
    manifest_files = release_files_from_manifest(root)
    return manifest_files if manifest_files is not None else discover_release_files(root)


def build_package(root: Path, output: Path, write: bool = False, force: bool = False) -> dict:
    manifest_files = release_files_from_manifest(root)
    files = manifest_files if manifest_files is not None else discover_release_files(root)
    inventory_source = "manifest" if manifest_files is not None else "discovery"
    output_path = (output if output.is_absolute() else root / output).resolve()
    release_check = build_release_report(root, strict=True)
    manifest_errors = [
        item
        for item in release_check["errors"]
        if item.get("message", "").startswith("template_manifest_")
    ]
    if manifest_files is None and not manifest_errors:
        manifest_errors.append({
            "path": MANIFEST_RELATIVE,
            "message": "template_manifest_required_for_release_pack",
        })
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
        "inventory_source": inventory_source,
        "files": [rel(path, root) for path in files],
        "ok": bool(files) and not output_errors and not manifest_errors and (release_check["ok"] or force),
        "forced": force,
        "output_errors": output_errors,
        "unforceable_errors": manifest_errors,
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
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in files:
                info = zipfile.ZipInfo(rel(path, root), date_time=DETERMINISTIC_ZIP_TIMESTAMP)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (0o100755 if path.suffix.casefold() == ".sh" else 0o100644) << 16
                archive.writestr(info, path.read_bytes())
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
        f"- Inventory: {report['inventory_source']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Strict release check: {'ok' if report['release_check']['ok'] else 'failed'}",
    ]
    if report.get("bytes") is not None:
        lines.append(f"- Bytes: {report['bytes']}")
    if report["output_errors"]:
        lines.extend(f"- Output error: {error}" for error in report["output_errors"])
    if report["unforceable_errors"]:
        lines.extend(
            f"- Unforceable error: {item['path']}: {item['message']}"
            for item in report["unforceable_errors"]
        )
    lines.extend(["", "Included files:"])
    lines.extend(f"- {path}" for path in report["files"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or write a clean Harness template zip package.")
    parser.add_argument("--root", type=Path, default=None, help="Template root. Defaults to nearest Harness root.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Zip path. Relative paths are resolved from root.")
    parser.add_argument("--write", action="store_true", help="Actually write the zip package.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass non-manifest strict hygiene failures only. Manifest integrity and output safety always block writes.",
    )
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
