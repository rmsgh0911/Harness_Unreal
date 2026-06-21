"""Summarize recent Harness cycle logs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, find_project_root, print_text_or_json, read_text, rel


VALID_DECISIONS = {"continue", "stop_success", "stop_blocked"}
PLACEHOLDER_VALUES = {"", "none", "record needed"}


def unique_recorded(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.casefold() not in PLACEHOLDER_VALUES))


def analyze_iteration(sections: list[dict]) -> dict:
    numbered = [section for section in sections if section["cycle_number"] is not None]
    numbers = [section["cycle_number"] for section in numbered]
    budgets = {section["max_cycles"] for section in numbered if section["max_cycles"] is not None}
    warnings: list[str] = []
    if len(numbers) != len(set(numbers)):
        warnings.append("duplicate cycle numbers")
    if numbers and numbers != list(range(1, max(numbers) + 1)):
        warnings.append("cycle numbers are not a contiguous 1-based sequence")
    if len(budgets) > 1:
        warnings.append("cycle budget changed within one log")
    invalid_decisions = sorted({section["decision"] for section in numbered if section["decision"] and section["decision"] not in VALID_DECISIONS})
    if invalid_decisions:
        warnings.append("invalid decisions: " + ", ".join(invalid_decisions))
    for section in numbered[:-1]:
        if section["decision"].startswith("stop_"):
            warnings.append(f"cycle {section['cycle_number']} stops before a later cycle")
            break
    budget = next(iter(budgets)) if len(budgets) == 1 else None
    current = max(numbers, default=0)
    if budget is not None and current > budget:
        warnings.append("cycle number exceeds budget")
    return {
        "current_cycle": current,
        "max_cycles": budget,
        "latest_decision": numbered[-1]["decision"] if numbered else "",
        "warnings": warnings,
    }


def parse_cycle_file(path: Path) -> dict:
    text = read_text(path)
    sections: list[dict] = []
    current: dict | None = None
    current_key: str | None = None
    labels = {"Changed": "changed", "Verified": "verified", "Remaining": "remaining", "Success Criteria": "success_criteria"}
    for line in text.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            legacy_number = re.search(r"\bCycle\s+(\d+)\b", title, flags=re.IGNORECASE)
            current = {
                "title": title,
                "worker": "",
                "cycle_number": int(legacy_number.group(1)) if legacy_number else None,
                "max_cycles": None,
                "decision": "",
                "success_criteria": [],
                "changed": [],
                "verified": [],
                "remaining": [],
            }
            sections.append(current)
            current_key = None
            continue
        if not current:
            continue
        stripped = line.strip()
        if stripped.startswith("- Worker:"):
            current["worker"] = stripped.removeprefix("- Worker:").strip()
            continue
        if stripped.startswith("- Cycle:"):
            match = re.fullmatch(r"(\d+)(?:/(\d+))?", stripped.removeprefix("- Cycle:").strip())
            if match:
                current["cycle_number"] = int(match.group(1))
                current["max_cycles"] = int(match.group(2)) if match.group(2) else None
            continue
        if stripped.startswith("- Decision:"):
            current["decision"] = stripped.removeprefix("- Decision:").strip()
            continue
        matched = False
        for label, key in labels.items():
            prefix = f"- {label}:"
            if stripped.startswith(prefix):
                current[key].append(stripped.removeprefix(prefix).strip())
                current_key = key
                matched = True
                break
        if not matched and current_key and stripped.startswith("- "):
            current[current_key].append(stripped[2:].strip())
    return {"path": path, "sections": sections, "lines": len(text.splitlines()), "iteration": analyze_iteration(sections)}


def build_summary(root: Path, limit: int = 5) -> dict:
    cycles = cycles_dir(root)
    files = sorted(
        (path for path in cycles.glob("*.md") if path.name != ".gitkeep"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if cycles.exists() else []
    parsed = [parse_cycle_file(path) for path in files[:limit]]
    changed: list[str] = []
    verified: list[str] = []
    remaining: list[str] = []
    total_sections = 0
    latest_decision = next(
        (section["decision"] for item in parsed for section in reversed(item["sections"]) if section["decision"]),
        "",
    )
    iteration_warnings: list[str] = []
    for item in parsed:
        iteration_warnings.extend(f"{rel(item['path'], root)}: {warning}" for warning in item["iteration"]["warnings"])
        for section in item["sections"]:
            total_sections += 1
            changed.extend(section["changed"])
            verified.extend(section["verified"])
        if item["sections"]:
            remaining.extend(item["sections"][-1]["remaining"])
    return {
        "root": str(root),
        "cycle_dir_exists": cycles.exists(),
        "file_count": len(files),
        "cycle_count": total_sections,
        "latest_decision": latest_decision,
        "iteration_warnings": iteration_warnings,
        "selected": [{"path": rel(item["path"], root), "sections": len(item["sections"]), "lines": item["lines"]} for item in parsed],
        "recent_changed": unique_recorded(changed)[-12:],
        "recent_verified": unique_recorded(verified)[-12:],
        "open_remaining": unique_recorded(remaining)[:12],
    }


def format_text(summary: dict) -> str:
    lines = [
        "Harness Cycle Summary",
        f"- Root: {summary['root']}",
        f"- Cycle files: {summary['file_count']}",
        f"- Parsed cycles: {summary['cycle_count']}",
        f"- Latest decision: {summary['latest_decision'] or 'not recorded'}",
        f"- Iteration warnings: {len(summary['iteration_warnings'])}",
        "",
        "Selected:",
    ]
    lines.extend(f"- {item['path']}: {item['sections']} sections, {item['lines']} lines" for item in summary["selected"]) if summary["selected"] else lines.append("- none")
    if summary["iteration_warnings"]:
        lines.extend(["", "Iteration Warnings:", *(f"- {warning}" for warning in summary["iteration_warnings"])])
    for key, title in [("recent_changed", "Recent Changed"), ("recent_verified", "Recent Verified"), ("open_remaining", "Open Remaining")]:
        lines.extend(["", f"{title}:"])
        lines.extend(f"- {item}" for item in summary[key]) if summary[key] else lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize recently modified Harness cycle logs.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recently modified cycle files to summarize.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    root = find_project_root(args.root)
    summary = build_summary(root, limit=args.limit)
    print_text_or_json(summary if args.json else format_text(summary), args.json)


if __name__ == "__main__":
    main()
