"""Scan an Unreal project and print compact configuration candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, load_json, rel, print_text_or_json


SKIP_DIRS = {"Binaries", "Intermediate", "Saved", "DerivedDataCache", ".git", ".vs"}


def safe_rglob(root: Path, pattern: str, limit: int = 200) -> tuple[list[Path], bool]:
    found: list[Path] = []
    truncated = False
    for path in root.rglob(pattern):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
        if len(found) >= limit:
            truncated = True
            break
    return sorted(found), truncated


def parse_uproject(path: Path) -> dict:
    data = load_json(path, {}) or {}
    modules = [item.get("Name") for item in data.get("Modules", []) if item.get("Name")]
    plugins = [item.get("Name") for item in data.get("Plugins", []) if item.get("Name")]
    return {
        "file": path.name,
        "engine_association": data.get("EngineAssociation", ""),
        "modules": modules,
        "plugins": plugins,
    }


def scan(root: Path, include_assets: bool = False) -> dict:
    uprojects = [parse_uproject(path) for path in sorted(root.glob("*.uproject"))]
    source_dir = root / "Source"
    config_dir = root / "Config"
    plugins_dir = root / "Plugins"

    build_cs, build_cs_truncated = safe_rglob(source_dir, "*.Build.cs") if source_dir.exists() else ([], False)
    targets, targets_truncated = safe_rglob(source_dir, "*Target.cs") if source_dir.exists() else ([], False)
    configs = sorted(config_dir.glob("*.ini")) if config_dir.exists() else []
    plugins, plugins_truncated = safe_rglob(plugins_dir, "*.uplugin") if plugins_dir.exists() else ([], False)
    maps, maps_truncated = safe_rglob(root / "Content", "*.umap", limit=80) if include_assets and (root / "Content").exists() else ([], False)

    module_names = sorted({path.stem.removesuffix(".Build") for path in build_cs})
    editor_targets = sorted(path.stem for path in targets if "Editor" in path.stem)
    game_targets = sorted(path.stem for path in targets if "Editor" not in path.stem)

    project_json_candidate = {
        "project_name": uprojects[0]["file"].removesuffix(".uproject") if len(uprojects) == 1 else "",
        "uproject_file": uprojects[0]["file"] if len(uprojects) == 1 else "",
        "engine_version": uprojects[0]["engine_association"] if len(uprojects) == 1 else "",
        "required_uproject_plugins": [],
        "build": {
            "editor_target_name": editor_targets[0] if len(editor_targets) == 1 else "",
            "game_target_name": game_targets[0] if len(game_targets) == 1 else "",
        },
    }

    return {
        "root": str(root),
        "uprojects": uprojects,
        "source": {
            "exists": source_dir.exists(),
            "modules": module_names,
            "build_cs": [rel(path, root) for path in build_cs],
            "targets": [rel(path, root) for path in targets],
            "editor_targets": editor_targets,
            "game_targets": game_targets,
            "truncated": build_cs_truncated or targets_truncated,
        },
        "config": {
            "exists": config_dir.exists(),
            "ini_files": [rel(path, root) for path in configs],
        },
        "plugins": {
            "exists": plugins_dir.exists(),
            "uplugin_files": [rel(path, root) for path in plugins],
            "truncated": plugins_truncated,
        },
        "content": {
            "maps_included": include_assets,
            "map_files": [rel(path, root) for path in maps],
            "truncated": maps_truncated,
        },
        "project_json_candidate": project_json_candidate,
    }


def format_text(result: dict) -> str:
    lines = [
        "Harness Unreal Scan",
        f"- Root: {result['root']}",
        f"- UProject files: {len(result['uprojects'])}",
        f"- Modules: {', '.join(result['source']['modules']) or 'none found'}",
        f"- Targets: {', '.join(result['source']['targets']) or 'none found'}",
        f"- Config files: {len(result['config']['ini_files'])}",
        f"- Plugins: {len(result['plugins']['uplugin_files'])}",
    ]
    if result["content"]["maps_included"]:
        lines.append(f"- Maps: {len(result['content']['map_files'])}")
    lines.append("")
    lines.append("project.json candidate:")
    lines.append(json.dumps(result["project_json_candidate"], ensure_ascii=False, indent=2))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Unreal project structure for Harness config candidates.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--include-assets", action="store_true", help="Also scan Content/*.umap. Skipped by default for speed.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    result = scan(root, include_assets=args.include_assets)
    print_text_or_json(result if args.json else format_text(result), args.json)


if __name__ == "__main__":
    main()
