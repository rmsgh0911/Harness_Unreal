"""Report risky working-tree changes for Harness/Unreal projects."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, rel, print_text_or_json


GENERATED_DIRS = {"Binaries", "Intermediate", "Saved", "DerivedDataCache"}
BINARY_ASSET_SUFFIXES = {".uasset", ".umap"}
PUBLIC_API_MARKERS = ("UFUNCTION", "UPROPERTY", "UCLASS", "USTRUCT", "UENUM")
PROGRESS_PATH = "Harness/docs/Progress.md"
PROGRESS_TRIGGER_PREFIXES = (
    "Source/",
    "Config/",
    "Content/",
    "Plugins/",
    "Harness/scripts/unreal/",
    "Harness/docs/FluxityPntSample/",
)
PROGRESS_TRIGGER_SUFFIXES = {
    ".uasset",
    ".umap",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".ini",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
}


def resolve_git_executable() -> str | None:
    found = shutil.which("git")
    if found:
        return found
    for candidate in [
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files/Git/bin/git.exe"),
        Path("C:/Program Files (x86)/Git/cmd/git.exe"),
        Path("C:/Program Files (x86)/Git/bin/git.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def run_git_status(root: Path) -> tuple[bool, list[str]]:
    git_executable = resolve_git_executable()
    if not git_executable:
        return False, []
    try:
        top_level = subprocess.run(
            [git_executable, "rev-parse", "--show-toplevel"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if top_level.returncode != 0:
            return False, []
        git_root = Path(top_level.stdout.strip()).resolve()
        if git_root != root.resolve():
            return False, []
        completed = subprocess.run(
            [git_executable, "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        return False, []
    if completed.returncode != 0:
        return False, []
    return True, [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def changed_path_from_status(line: str) -> str:
    text = line[3:] if len(line) > 3 else line
    if " -> " in text:
        text = text.rsplit(" -> ", 1)[-1]
    return text.strip().strip('"')


def scan_without_git(root: Path) -> list[str]:
    candidates: list[str] = []
    for directory in GENERATED_DIRS:
        path = root / directory
        if path.exists():
            candidates.append(f"?? {directory}/")
    return candidates


def classify(paths: list[str]) -> dict:
    risks: list[dict] = []
    for status_line in paths:
        path_text = changed_path_from_status(status_line)
        parts = Path(path_text).parts
        suffix = Path(path_text).suffix.lower()
        if any(part in GENERATED_DIRS for part in parts):
            risks.append({"level": "high", "path": path_text, "reason": "generated_directory"})
        if suffix in BINARY_ASSET_SUFFIXES:
            risks.append({"level": "medium", "path": path_text, "reason": "binary_unreal_asset"})
        if path_text.endswith(".Build.cs"):
            risks.append({"level": "medium", "path": path_text, "reason": "module_dependency_change"})
        if path_text.startswith("Source/") and suffix in {".h", ".hpp"}:
            risks.append({"level": "low", "path": path_text, "reason": "header_or_public_api_review_needed"})
    return {
        "changed_count": len(paths),
        "changed": paths,
        "risks": risks,
        "risk_count": len(risks),
    }


def inspect_public_api_markers(root: Path, report: dict) -> None:
    marker_hits: list[dict] = []
    for item in report["changed"]:
        path_text = changed_path_from_status(item)
        path = root / path_text
        if not path.exists() or path.suffix.lower() not in {".h", ".hpp", ".cpp"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        hits = [marker for marker in PUBLIC_API_MARKERS if marker in text]
        if hits:
            marker_hits.append({"path": path_text, "markers": hits})
    report["public_api_marker_hits"] = marker_hits


def inspect_progress_recording(report: dict) -> None:
    changed_paths = [changed_path_from_status(item).replace("\\", "/") for item in report["changed"]]
    progress_changed = PROGRESS_PATH in changed_paths
    meaningful_paths: list[str] = []
    for path_text in changed_paths:
        if path_text == PROGRESS_PATH:
            continue
        suffix = Path(path_text).suffix.lower()
        if path_text.startswith(PROGRESS_TRIGGER_PREFIXES) or suffix in BINARY_ASSET_SUFFIXES:
            if suffix in PROGRESS_TRIGGER_SUFFIXES or path_text.startswith(("Content/", "Source/", "Config/", "Plugins/")):
                meaningful_paths.append(path_text)
    report["progress_recording"] = {
        "progress_path": PROGRESS_PATH,
        "progress_changed": progress_changed,
        "meaningful_change_count": len(meaningful_paths),
        "meaningful_changes_sample": meaningful_paths[:20],
        "update_recommended": bool(meaningful_paths and not progress_changed),
    }


def build_report(root: Path) -> dict:
    git_available, changed = run_git_status(root)
    if not git_available:
        changed = scan_without_git(root)
    report = classify(changed)
    reliable_change_list = git_available
    report.update(
        {
            "root": str(root),
            "git_available": git_available,
            "git_directory_exists": (root / ".git").exists(),
            "change_list_reliable": reliable_change_list,
            "mode": "git_status" if git_available else "limited_generated_directory_scan",
            "ok": not any(risk["level"] == "high" for risk in report["risks"]),
        }
    )
    inspect_public_api_markers(root, report)
    inspect_progress_recording(report)
    if report["progress_recording"]["update_recommended"]:
        report["ok"] = False
    return report


def format_text(report: dict) -> str:
    lines = [
        "Harness Diff Guard",
        f"- Root: {report['root']}",
        f"- Git available: {report['git_available']}",
        f"- Git directory exists: {report['git_directory_exists']}",
        f"- Mode: {report['mode']}",
        f"- Changed paths: {report['changed_count'] if report['change_list_reliable'] else 'limited scan only'}",
        f"- Risks: {report['risk_count']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
    ]
    if not report["change_list_reliable"]:
        lines.append("- Note: git was not available, so ordinary file changes cannot be listed.")
    if report["risks"]:
        lines.append("")
        lines.append("Risks:")
        for risk in report["risks"]:
            lines.append(f"- [{risk['level']}] {risk['path']}: {risk['reason']}")
    if report.get("progress_recording", {}).get("update_recommended"):
        progress = report["progress_recording"]
        lines.append("")
        lines.append("Progress recording:")
        lines.append(f"- Update recommended: {progress['progress_path']} is not changed, but meaningful project changes are pending.")
        for path_text in progress["meaningful_changes_sample"][:10]:
            lines.append(f"- {path_text}")
    if report.get("public_api_marker_hits"):
        lines.append("")
        lines.append("Public API marker hits:")
        for hit in report["public_api_marker_hits"]:
            lines.append(f"- {hit['path']}: {', '.join(hit['markers'])}")
    if report["changed"]:
        lines.append("")
        lines.append("Changed:")
        lines.extend(f"- {changed_path_from_status(item)}" for item in report["changed"][:40])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize risky changes in the current Harness project.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root)
    print_text_or_json(report if args.json else format_text(report), args.json)


if __name__ == "__main__":
    main()
