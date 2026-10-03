"""Summarize recent Harness cycle logs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, find_project_root, print_text_or_json, read_text, rel


VALID_DECISIONS = {"continue", "stop_success", "stop_blocked"}
VALID_BUDGET_MODES = {"exact_count", "upper_bound"}
PLACEHOLDER_VALUES = {"", "none", "record needed"}
ARTIFACT_REQUIRED_KINDS = {"render", "interaction", "live_service"}
EVIDENCE_GAP_STATUSES = {
    "invalidated",
    "verification_failed",
    "invalid_exit_code",
    "acceptance_failed",
    "acceptance_unknown",
    "missing_artifact",
    "pending_acceptance",
    "revision_mismatch",
    "skipped",
    "invalid_metadata",
    "missing_revision",
    "missing_scope",
    "acceptance_required",
}


def unique_recorded(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.casefold() not in PLACEHOLDER_VALUES))


def evidence_status(section: dict) -> str:
    if section.get("metadata_errors"):
        return "invalid_metadata"
    if set(section.get("evidence_kinds", [])) - {"structure", "runtime", "render", "interaction", "live_service"}:
        return "invalid_metadata"
    if section.get("acceptance", "") not in {"", "passed", "pending", "failed", "skipped", "not_required"}:
        return "invalid_metadata"
    if section.get("invalidated"):
        return "invalidated"
    exit_codes = section.get("evidence_exit_codes", [])
    if any(not re.fullmatch(r"-?\d+", str(code).strip()) for code in exit_codes):
        return "invalid_exit_code"
    if any(int(code) != 0 for code in exit_codes):
        return "verification_failed"
    input_revision = section.get("input_revision", "")
    artifact_revision = section.get("artifact_revision", "")
    if input_revision and artifact_revision and input_revision != artifact_revision:
        return "revision_mismatch"
    acceptance = section.get("acceptance", "")
    if acceptance == "skipped":
        return "skipped"
    if acceptance == "failed":
        return "acceptance_failed"
    if acceptance == "pending":
        return "pending_acceptance"
    kinds = set(section.get("evidence_kinds", []))
    artifacts = unique_recorded(section.get("artifacts", []))
    if kinds & ARTIFACT_REQUIRED_KINDS and acceptance in {"passed", "not_required"}:
        if not artifacts:
            return "missing_artifact"
        if not input_revision or not artifact_revision:
            return "missing_revision"
        if not unique_recorded(section.get("scopes", [])):
            return "missing_scope"
        if acceptance == "not_required":
            return "acceptance_required"
    if acceptance == "passed":
        if kinds & ARTIFACT_REQUIRED_KINDS and not artifacts:
            return "missing_artifact"
        return "accepted"
    if acceptance == "not_required":
        return "not_required"
    if kinds & ARTIFACT_REQUIRED_KINDS and not artifacts:
        return "missing_artifact"
    if kinds:
        return "acceptance_unknown"
    return "legacy_unknown"


def analyze_iteration(sections: list[dict]) -> dict:
    numbered = [section for section in sections if section["cycle_number"] is not None]
    numbers = [section["cycle_number"] for section in numbered]
    budgets = {section["max_cycles"] for section in numbered if section["max_cycles"] is not None}
    budget_modes = {section.get("budget_mode", "") for section in numbered if section.get("budget_mode")}
    warnings: list[str] = []
    warnings.extend(f"{section.get('title', 'entry')}: {error}"
                    for section in sections for error in section.get("metadata_errors", []))
    if len(numbers) != len(set(numbers)):
        warnings.append("duplicate cycle numbers")
    if numbers and numbers != list(range(1, max(numbers) + 1)):
        warnings.append("cycle numbers are not a contiguous 1-based sequence")
    if len(budgets) > 1:
        warnings.append("cycle budget changed within one log")
    if len(budget_modes) > 1:
        warnings.append("cycle budget mode changed within one log")
    invalid_budget_modes = sorted(budget_modes - VALID_BUDGET_MODES)
    if invalid_budget_modes:
        warnings.append("invalid budget modes: " + ", ".join(invalid_budget_modes))
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
    if budget is not None and budget_modes == {"exact_count"} and numbered and numbered[-1]["decision"] == "stop_success" and current != budget:
        warnings.append("exact-count work cannot stop successfully before its requested budget")
    return {
        "current_cycle": current,
        "max_cycles": budget,
        "budget_mode": next(iter(budget_modes)) if len(budget_modes) == 1 else "",
        "latest_decision": numbered[-1]["decision"] if numbered else "",
        "warnings": warnings,
    }


def parse_cycle_file(path: Path) -> dict:
    return parse_cycle_text(read_text(path), path)


def parse_cycle_text(text: str, path: Path = Path("")) -> dict:
    sections: list[dict] = []
    current: dict | None = None
    current_key: str | None = None
    labels = {
        "Changed": "changed",
        "Verified": "verified",
        "Remaining": "remaining",
        "Success Criteria": "success_criteria",
        "Claim": "claims",
        "Evidence Kind": "evidence_kinds",
        "Evidence Command": "evidence_commands",
        "Evidence Exit Code": "evidence_exit_codes",
        "Artifact": "artifacts",
        "Scope": "scopes",
        "Supersedes": "supersedes",
    }
    fence = ""
    fence_length = 0
    metadata_seen: dict[str, str] = {}
    scalar_prefixes = {"Worker", "Cycle", "Decision", "Recorded", "Budget Mode", "Input Revision", "Artifact Revision", "Acceptance", "Invalidated"}
    for line_number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence and len(marker[1]) >= fence_length and not marker[2].strip():
                fence = ""
            continue
        if marker:
            fence, fence_length = marker[1][0], len(marker[1])
            current_key = None
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            legacy_number = re.search(r"\bCycle\s+(\d+)\b", title, flags=re.IGNORECASE)
            current = {
                "title": title,
                "line": line_number,
                "recorded_at": "",
                "worker": "",
                "cycle_number": int(legacy_number.group(1)) if legacy_number else None,
                "max_cycles": None,
                "budget_mode": "",
                "decision": "",
                "success_criteria": [],
                "changed": [],
                "verified": [],
                "remaining": [],
                "claims": [],
                "evidence_kinds": [],
                "evidence_commands": [],
                "evidence_exit_codes": [],
                "artifacts": [],
                "input_revision": "",
                "artifact_revision": "",
                "scopes": [],
                "acceptance": "",
                "supersedes": [],
                "invalidated": False,
                "metadata_errors": [],
            }
            sections.append(current)
            current_key = None
            metadata_seen = {}
            continue
        if not current:
            continue
        stripped = line.strip()
        if not line.startswith("- "):
            if current_key and line.startswith("  - "):
                if current_key == "evidence_exit_codes" and current[current_key] and current[current_key][-1] == "":
                    current[current_key].pop()
                current[current_key].append(stripped[2:].strip())
            elif stripped:
                current_key = None
            continue
        label, separator, value = stripped[2:].partition(":")
        if separator and label in scalar_prefixes:
            value = value.strip()
            if label in metadata_seen and metadata_seen[label] != value:
                current["metadata_errors"].append(f"conflicting duplicate metadata: {label}")
                current_key = None
                continue
            metadata_seen[label] = value
        if stripped.startswith("- Worker:"):
            current["worker"] = stripped.removeprefix("- Worker:").strip()
            current_key = None
            continue
        if stripped.startswith("- Cycle:"):
            match = re.fullmatch(r"(\d+)(?:/(\d+))?", stripped.removeprefix("- Cycle:").strip())
            if match:
                current["cycle_number"] = int(match.group(1))
                current["max_cycles"] = int(match.group(2)) if match.group(2) else None
                if current["cycle_number"] < 1 or current["max_cycles"] == 0:
                    current["metadata_errors"].append("cycle numbers and budgets must be positive")
            else:
                current["metadata_errors"].append("malformed Cycle metadata")
            current_key = None
            continue
        if stripped.startswith("- Decision:"):
            current["decision"] = stripped.removeprefix("- Decision:").strip()
            current_key = None
            continue
        scalar_labels = {
            "- Recorded:": "recorded_at",
            "- Budget Mode:": "budget_mode",
            "- Input Revision:": "input_revision",
            "- Artifact Revision:": "artifact_revision",
            "- Acceptance:": "acceptance",
        }
        scalar_matched = False
        for prefix, key in scalar_labels.items():
            if stripped.startswith(prefix):
                current[key] = stripped.removeprefix(prefix).strip()
                current_key = None
                scalar_matched = True
                break
        if scalar_matched:
            continue
        if stripped.startswith("- Invalidated:"):
            if value.casefold() not in {"true", "yes", "1", "false", "no", "0"}:
                current["metadata_errors"].append("malformed Invalidated metadata")
            current["invalidated"] = stripped.removeprefix("- Invalidated:").strip().casefold() in {"true", "yes", "1"}
            current_key = None
            continue
        matched = False
        for label, key in labels.items():
            prefix = f"- {label}:"
            if stripped.startswith(prefix):
                value = stripped.removeprefix(prefix).strip()
                current[key].append(value)
                current_key = key
                matched = True
                break
        if not matched and stripped:
            current_key = None
    for section in sections:
        section["evidence_status"] = evidence_status(section)
    return {"path": path, "sections": sections, "lines": len(text.splitlines()), "iteration": analyze_iteration(sections)}


def build_summary(root: Path, limit: int = 5) -> dict:
    cycles = cycles_dir(root)
    files = sorted(
        (path for path in cycles.glob("*.md") if path.name != ".gitkeep"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if cycles.exists() else []
    parsed = [parse_cycle_file(path) for path in files[:limit]]
    from harness_knowledge import _apply_replacements

    routing_records = []
    for item in parsed:
        for section in item["sections"]:
            relative = rel(item["path"], root)
            routing_records.append({"path": relative, "section": section["title"],
                                    "reference": f"{relative}#{section['title']}",
                                    "invalidated": section["invalidated"], "supersedes": section["supersedes"]})
    _apply_replacements(routing_records)
    routing_status = {item["reference"]: item["status"] for item in routing_records}
    changed: list[str] = []
    verified: list[str] = []
    remaining: list[str] = []
    total_sections = 0
    latest_decision = next(
        (section["decision"] for item in parsed for section in reversed(item["sections"]) if section["decision"]),
        "",
    )
    iteration_warnings: list[str] = []
    evidence_gaps: list[dict] = []
    for item in parsed:
        iteration_warnings.extend(f"{rel(item['path'], root)}: {warning}" for warning in item["iteration"]["warnings"])
        for section in item["sections"]:
            total_sections += 1
            changed.extend(section["changed"])
            reference = f"{rel(item['path'], root)}#{section['title']}"
            if section.get("evidence_status") not in EVIDENCE_GAP_STATUSES and routing_status[reference] == "current":
                verified.extend(section["verified"])
            if section.get("evidence_status") in EVIDENCE_GAP_STATUSES:
                evidence_gaps.append({
                    "path": rel(item["path"], root),
                    "title": section["title"],
                    "status": section["evidence_status"],
                    "scopes": section.get("scopes", []),
                })
        if item["sections"]:
            remaining.extend(item["sections"][-1]["remaining"])
    return {
        "root": str(root),
        "cycle_dir_exists": cycles.exists(),
        "file_count": len(files),
        "cycle_count": total_sections,
        "latest_decision": latest_decision,
        "iteration_warnings": iteration_warnings,
        "evidence_gaps": evidence_gaps,
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
        f"- Evidence gaps: {len(summary['evidence_gaps'])}",
        "",
        "Selected:",
    ]
    lines.extend(f"- {item['path']}: {item['sections']} sections, {item['lines']} lines" for item in summary["selected"]) if summary["selected"] else lines.append("- none")
    if summary["iteration_warnings"]:
        lines.extend(["", "Iteration Warnings:", *(f"- {warning}" for warning in summary["iteration_warnings"])])
    if summary["evidence_gaps"]:
        lines.extend(["", "Evidence Gaps:"])
        lines.extend(
            f"- {item['path']} > {item['title']}: {item['status']}"
            for item in summary["evidence_gaps"]
        )
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
