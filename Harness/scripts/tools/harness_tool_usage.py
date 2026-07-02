"""Audit how well each Harness tool is wired in, to surface consolidation candidates.

This is a static reference audit, not runtime telemetry: as the tool count grows
past twenty, it answers "which tools does nothing reference?" so rarely-used tools
can be merged or retired instead of quietly raising maintenance cost.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel


# Tools invoked by these orchestrators are exercised on nearly every task, so a
# reference here counts as "actively wired in" regardless of doc mentions.
ORCHESTRATOR_FILES = ("harness_verify_all.py", "harness_context.py")
# harness_common is a shared library, not a standalone tool.
NON_TOOL_MODULES = {"harness_common"}


def _doc_files(root: Path) -> list[Path]:
    harness = harness_dir(root)
    candidates = [
        root / "HARNESS.md",
        root / "README.md",
        root / "AGENTS.md",
        root / "CLAUDE.md",
        harness / "README.md",
        harness / "scripts" / "tools" / "README.md",
    ]
    docs_dir = harness / "docs"
    if docs_dir.exists():
        candidates.extend(sorted(docs_dir.rglob("*.md")))
    return [path for path in candidates if path.is_file()]


def build_report(root: Path) -> dict:
    tools_dir = harness_dir(root) / "scripts" / "tools"
    tool_paths = sorted(path for path in tools_dir.glob("*.py") if path.stem not in NON_TOOL_MODULES)

    manifest = load_json(tools_dir / "tool_manifest.json", {}) or {}
    registered = {str(tool.get("name", "")) for tool in manifest.get("tools", []) if isinstance(tool, dict)}

    doc_files = _doc_files(root)
    doc_texts = {rel(path, root): read_text(path) for path in doc_files}
    tool_texts = {path.stem: read_text(path) for path in tool_paths}

    tools: list[dict] = []
    for path in tool_paths:
        name = path.stem
        doc_refs = sorted(doc_rel for doc_rel, text in doc_texts.items() if name in text)
        tool_refs = sorted(
            other for other, text in tool_texts.items() if other != name and name in text
        )
        wired = any(name in tool_texts.get(orchestrator[:-3], "") for orchestrator in ORCHESTRATOR_FILES)
        in_manifest = name in registered
        low_reference = not wired and not doc_refs and not tool_refs
        tools.append({
            "name": name,
            "registered_in_manifest": in_manifest,
            "wired_into_orchestrator": wired,
            "doc_reference_count": len(doc_refs),
            "tool_reference_count": len(tool_refs),
            "doc_references": doc_refs,
            "tool_references": tool_refs,
            "low_reference": low_reference,
        })

    low_reference = [tool["name"] for tool in tools if tool["low_reference"]]
    unregistered = [tool["name"] for tool in tools if not tool["registered_in_manifest"]]
    return {
        "root": str(root),
        "ok": True,
        "tool_count": len(tools),
        "low_reference": low_reference,
        "unregistered": unregistered,
        "tools": tools,
        "guidance": [
            "low_reference tools are wired into no orchestrator and mentioned in no doc or other tool; review them for consolidation or removal.",
            "This audit counts static references, not runtime frequency; confirm intent before removing a tool.",
        ],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Tool Usage",
        f"- Root: {report['root']}",
        f"- Tools: {report['tool_count']}",
        f"- Low reference: {', '.join(report['low_reference']) or 'none'}",
        f"- Unregistered: {', '.join(report['unregistered']) or 'none'}",
        "",
        "Per tool (doc refs / tool refs / wired):",
    ]
    for tool in report["tools"]:
        flag = "  <-- review" if tool["low_reference"] else ""
        lines.append(
            f"- {tool['name']}: {tool['doc_reference_count']} / {tool['tool_reference_count']} / "
            f"{'yes' if tool['wired_into_orchestrator'] else 'no'}{flag}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Harness tool references to find consolidation candidates.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    report = build_report(root)
    print(dump_json(report) if args.json else format_text(report))


if __name__ == "__main__":
    main()
