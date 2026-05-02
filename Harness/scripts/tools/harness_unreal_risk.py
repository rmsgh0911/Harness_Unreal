"""Summarize Unreal-specific risks from changed files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, read_text, print_text_or_json
from harness_diff_guard import build_report as build_diff_report, changed_path_from_status


HEADER_MARKERS = ["UCLASS", "USTRUCT", "UENUM", "UFUNCTION", "UPROPERTY", "DECLARE_DYNAMIC"]
CONFIG_HINTS = ["DefaultEngine.ini", "DefaultInput.ini", "DefaultGame.ini"]


def classify_path(path_text: str) -> list[dict]:
    path = Path(path_text)
    suffix = path.suffix.lower()
    risks: list[dict] = []
    if path_text.endswith(".Build.cs"):
        risks.append({"level": "high", "reason": "module dependency or build rules changed"})
    if path_text.startswith("Source/") and suffix in {".h", ".hpp"}:
        risks.append({"level": "medium", "reason": "header change may affect public API or Blueprint surface"})
    if path_text.startswith("Config/") and path.name in CONFIG_HINTS:
        risks.append({"level": "medium", "reason": "core Unreal config changed"})
    if suffix in {".uasset", ".umap"}:
        risks.append({"level": "medium", "reason": "binary asset changed; describe manual editor validation"})
    if "/Public/" in path_text.replace("\\", "/"):
        risks.append({"level": "medium", "reason": "Public header/module boundary changed"})
    return risks


def marker_hits(root: Path, path_text: str) -> list[str]:
    path = root / path_text
    if not path.exists() or path.suffix.lower() not in {".h", ".hpp", ".cpp"}:
        return []
    text = read_text(path)
    return [marker for marker in HEADER_MARKERS if marker in text]


def build_report(root: Path) -> dict:
    diff = build_diff_report(root)
    items: list[dict] = []
    for status_line in diff["changed"]:
        path_text = changed_path_from_status(status_line)
        risks = classify_path(path_text)
        markers = marker_hits(root, path_text)
        if markers:
            risks.append({"level": "medium", "reason": "Unreal reflection or delegate marker present: " + ", ".join(markers)})
        if risks:
            items.append({"path": path_text, "risks": risks})
    high = sum(1 for item in items for risk in item["risks"] if risk["level"] == "high")
    medium = sum(1 for item in items for risk in item["risks"] if risk["level"] == "medium")
    recommendations = []
    if high:
        recommendations.append("Run a real C++ build and review module dependencies.")
    if medium:
        recommendations.append("Record any required PIE/manual validation for Blueprint, config, input, asset, or map behavior.")
    return {
        "root": str(root),
        "git_available": diff["git_available"],
        "ok": high == 0,
        "changed_count": diff["changed_count"],
        "risk_files": items,
        "risk_count": sum(len(item["risks"]) for item in items),
        "high_count": high,
        "medium_count": medium,
        "recommendations": recommendations,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Unreal Risk",
        f"- Root: {report['root']}",
        f"- Git available: {report['git_available']}",
        f"- Changed paths: {report['changed_count']}",
        f"- Risks: {report['risk_count']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
    ]
    if report["risk_files"]:
        lines.append("")
        lines.append("Risk files:")
        for item in report["risk_files"]:
            lines.append(f"- {item['path']}")
            for risk in item["risks"]:
                lines.append(f"  - [{risk['level']}] {risk['reason']}")
    if report["recommendations"]:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in report["recommendations"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Unreal-specific risks from changed files.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root)
    print_text_or_json(report if args.json else format_text(report), args.json)


if __name__ == "__main__":
    main()
