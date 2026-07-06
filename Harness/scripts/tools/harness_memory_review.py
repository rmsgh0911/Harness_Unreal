"""Review whether finished work produced reusable Harness memory candidates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, rel
from harness_memory import memory_doctor, validate_memory


REVIEW_RULES = [
    {
        "prefixes": ("HARNESS.md", "AGENTS.md", "CLAUDE.md"),
        "reason": "agent operating rule changed",
        "candidate": "project rule",
    },
    {
        "prefixes": ("Harness/docs/template/", "Harness/docs/AgentFieldGuide.md"),
        "reason": "setup, migration, or field-guide routing changed",
        "candidate": "routing hint",
    },
    {
        "prefixes": ("Harness/scripts/tools/",),
        "reason": "repeatable Harness tool behavior changed",
        "candidate": "durable decision",
    },
    {
        "prefixes": ("Harness/config/", "Harness/index/"),
        "reason": "project routing, policy, or verification surface changed",
        "candidate": "routing hint",
    },
    {
        "prefixes": ("Harness/work/state.md", "Harness/work/next.md", "Harness/work/tasks/", "Harness/work/cycles/"),
        "reason": "work record may contain a reusable conclusion",
        "candidate": "reviewed lesson",
    },
]


def git_changed_paths(root: Path) -> dict:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return {"ok": False, "paths": [], "error": f"git status could not start: {exc}"}

    if completed.returncode != 0:
        output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
        return {"ok": False, "paths": [], "error": output or f"git status exited {completed.returncode}"}

    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1].strip()
        if path:
            paths.append(path.replace("\\", "/"))
    return {"ok": True, "paths": sorted(set(paths)), "error": ""}


def classify_memory_candidates(paths: list[str]) -> list[dict]:
    suggestions: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for path in paths:
        normalized = path.replace("\\", "/")
        for rule in REVIEW_RULES:
            if any(normalized == prefix or normalized.startswith(prefix) for prefix in rule["prefixes"]):
                key = (rule["candidate"], rule["reason"])
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append({
                    "candidate": rule["candidate"],
                    "reason": rule["reason"],
                    "example_path": normalized,
                })
                break

    return suggestions


def build_review(root: Path, changed_paths: list[str] | None = None) -> dict:
    changed_source = "argument"
    status_report = {"ok": True, "paths": changed_paths or [], "error": ""}
    if changed_paths is None:
        status_report = git_changed_paths(root)
        changed_paths = status_report["paths"]
        changed_source = "git_status"
    else:
        changed_paths = sorted(set(path.replace("\\", "/") for path in changed_paths))

    validation = validate_memory(root)
    doctor = memory_doctor(root)
    suggestions = classify_memory_candidates(changed_paths)

    return {
        "ok": bool(status_report["ok"]) and bool(validation.get("ok")),
        "root": str(root),
        "changed_source": changed_source,
        "changed_paths": changed_paths,
        "changed_paths_count": len(changed_paths),
        "review_recommended": bool(suggestions),
        "suggestions": suggestions,
        "memory_validation": validation,
        "memory_doctor": doctor,
        "errors": [
            *([] if status_report["ok"] else [{"error": status_report["error"]}]),
            *validation.get("errors", []),
        ],
        "guidance": [
            "Add memory only for reusable decisions, durable routing hints, or project rules that reduce future context loading.",
            "Do not store command logs, temporary state, long output, credentials, or unverified guesses.",
            "Use harness_memory.py --add for one compact reviewed entry when a suggestion is truly reusable.",
        ],
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Memory Review",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Changed paths: {report['changed_paths_count']} ({report['changed_source']})",
        f"- Review recommended: {'yes' if report['review_recommended'] else 'no'}",
    ]

    if report["suggestions"]:
        lines.append("")
        lines.append("Possible memory candidates:")
        for item in report["suggestions"]:
            lines.append(f"- {item['candidate']}: {item['reason']} ({item['example_path']})")

    doctor_findings = report.get("memory_doctor", {}).get("findings", [])
    if doctor_findings:
        lines.append("")
        lines.append("Memory doctor findings:")
        for item in doctor_findings[:5]:
            location = item.get("location", "")
            message = item.get("message", item.get("error", ""))
            lines.append(f"- {item.get('severity', 'info')}: {message} {location}".rstrip())

    if report["errors"]:
        lines.append("")
        lines.append("Errors:")
        for item in report["errors"]:
            lines.append(f"- {item.get('error', item)}")

    lines.append("")
    lines.append("Guidance:")
    lines.extend(f"- {item}" for item in report["guidance"])
    lines.append("- Example: python Harness/scripts/tools/harness_memory.py --add --title \"...\" --body \"...\" --tags harness,workflow --source HARNESS.md")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review whether finished work has compact Harness memory candidates.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--changed-path", action="append", default=None, help="Override changed path input; repeatable.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_review(root, changed_paths=args.changed_path)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
