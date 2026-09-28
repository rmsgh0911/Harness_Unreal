"""Prepare or append short Harness cycle log entries."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, dump_json, find_project_root, parse_date_text, read_text, rel, today_cycle_path, validate_task_id, write_text
from harness_cycle_summary import EVIDENCE_GAP_STATUSES, VALID_BUDGET_MODES, evidence_status, parse_cycle_file


EVIDENCE_KINDS = {"structure", "runtime", "render", "interaction", "live_service"}
ACCEPTANCE_VALUES = {"passed", "pending", "failed", "skipped", "not_required"}
ARTIFACT_REQUIRED_KINDS = {"render", "interaction", "live_service"}


def normalize_items(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned or [fallback]


def format_item_lines(label: str, items: list[str]) -> list[str]:
    first, *rest = items
    return [f"- {label}: {first}", *(f"  - {item}" for item in rest)]


def build_entry(
    title: str,
    changed: list[str],
    verified: list[str],
    remaining: list[str],
    worker: str = "",
    cycle_number: int | None = None,
    max_cycles: int | None = None,
    budget_mode: str = "",
    decision: str = "",
    success_criteria: list[str] | None = None,
    claims: list[str] | None = None,
    evidence_kinds: list[str] | None = None,
    evidence_commands: list[str] | None = None,
    evidence_exit_codes: list[str] | None = None,
    artifacts: list[str] | None = None,
    input_revision: str = "",
    artifact_revision: str = "",
    scopes: list[str] | None = None,
    acceptance: str = "",
    supersedes: list[str] | None = None,
    invalidated: bool = False,
) -> str:
    now = datetime.now().astimezone()
    lines = [f"## {now.strftime('%H:%M')} {title}", "", f"- Recorded: {now.isoformat(timespec='minutes')}"]
    if worker:
        lines.append(f"- Worker: {worker}")
    if cycle_number is not None:
        lines.append(f"- Cycle: {cycle_number}" + (f"/{max_cycles}" if max_cycles is not None else ""))
    if budget_mode:
        lines.append(f"- Budget Mode: {budget_mode}")
    if decision:
        lines.append(f"- Decision: {decision}")
    if success_criteria:
        lines.extend(format_item_lines("Success Criteria", normalize_items(success_criteria, "not recorded")))
    for label, values in [
        ("Claim", claims),
        ("Evidence Kind", evidence_kinds),
        ("Evidence Command", evidence_commands),
        ("Evidence Exit Code", evidence_exit_codes),
        ("Artifact", artifacts),
        ("Scope", scopes),
        ("Supersedes", supersedes),
    ]:
        if values:
            lines.extend(format_item_lines(label, normalize_items(values, "not recorded")))
    if input_revision:
        lines.append(f"- Input Revision: {input_revision.strip()}")
    if artifact_revision:
        lines.append(f"- Artifact Revision: {artifact_revision.strip()}")
    if acceptance:
        lines.append(f"- Acceptance: {acceptance}")
    if invalidated:
        lines.append("- Invalidated: true")
    lines.extend(format_item_lines("Changed", normalize_items(changed, "record needed")))
    lines.extend(format_item_lines("Verified", normalize_items(verified, "record needed")))
    lines.extend(format_item_lines("Remaining", normalize_items(remaining, "none")))
    return "\n".join(lines) + "\n"


def append_entry(path: Path, entry: str) -> None:
    existing = read_text(path)
    separator = "\n\n" if existing else ""
    write_text(path, existing.rstrip() + separator + entry)


def entry_count(path: Path) -> int:
    return sum(1 for line in read_text(path).splitlines() if line.startswith("## "))


def validate_evidence(
    evidence_kinds: list[str] | None,
    artifacts: list[str] | None,
    input_revision: str,
    artifact_revision: str,
    acceptance: str,
    decision: str,
    invalidated: bool,
) -> list[str]:
    kinds = set(evidence_kinds or [])
    errors: list[str] = []
    if not kinds <= EVIDENCE_KINDS:
        errors.append("unsupported evidence kind")
    if acceptance and acceptance not in ACCEPTANCE_VALUES:
        errors.append("unsupported acceptance value")
    if acceptance == "passed" and kinds & ARTIFACT_REQUIRED_KINDS and not any(item.strip() for item in artifacts or []):
        errors.append("passed render/interaction/live_service evidence requires an artifact")
    if input_revision and artifact_revision and input_revision.strip() != artifact_revision.strip():
        errors.append("artifact revision does not match input revision")
    if decision == "stop_success" and kinds & ARTIFACT_REQUIRED_KINDS and acceptance not in {"passed", "not_required"}:
        errors.append("stop_success requires passed or not_required acceptance for render/interaction/live_service evidence")
    if decision == "stop_success" and invalidated:
        errors.append("an invalidated entry cannot stop successfully")
    return errors


def validate_iteration_entry(
    path: Path,
    cycle_number: int | None,
    max_cycles: int | None,
    decision: str,
    *,
    budget_mode: str = "",
    evidence_kinds: list[str] | None = None,
    artifacts: list[str] | None = None,
    input_revision: str = "",
    artifact_revision: str = "",
    acceptance: str = "",
    invalidated: bool = False,
    evidence_exit_codes: list[str] | None = None,
) -> list[str]:
    if cycle_number is None:
        return []
    parsed = parse_cycle_file(path) if path.exists() else {"sections": [], "iteration": {"warnings": []}}
    sections = parsed["sections"]
    numbered = [section for section in sections if section.get("cycle_number") is not None]
    errors = [f"existing cycle log is invalid: {warning}" for warning in parsed["iteration"]["warnings"]]
    expected = len(sections) + 1
    if cycle_number != expected:
        errors.append(f"cycle number must be the next contiguous value: {expected}")
    recorded_budgets = {section["max_cycles"] for section in numbered if section.get("max_cycles") is not None}
    recorded_budget_modes = {section.get("budget_mode", "") for section in numbered if section.get("budget_mode")}
    if max_cycles is not None and recorded_budgets and recorded_budgets != {max_cycles}:
        errors.append(f"cycle budget must remain {next(iter(recorded_budgets))}")
    if budget_mode and budget_mode not in VALID_BUDGET_MODES:
        errors.append("unsupported budget mode")
    if budget_mode and recorded_budget_modes and recorded_budget_modes != {budget_mode}:
        errors.append(f"cycle budget mode must remain {next(iter(recorded_budget_modes))}")
    if numbered and numbered[-1].get("decision", "").startswith("stop_"):
        errors.append("cannot append after a stop decision")
    if max_cycles is not None and not decision:
        errors.append("--decision is required when --max-cycles is used")
    if max_cycles is not None and cycle_number == max_cycles and decision == "continue":
        errors.append("the final budgeted cycle must use stop_success or stop_blocked")
    errors.extend(validate_evidence(evidence_kinds, artifacts, input_revision, artifact_revision, acceptance, decision, invalidated))
    status = evidence_status({
        "evidence_kinds": evidence_kinds or [], "artifacts": artifacts or [],
        "input_revision": input_revision, "artifact_revision": artifact_revision,
        "acceptance": acceptance, "invalidated": invalidated,
        "evidence_exit_codes": evidence_exit_codes or [],
    })
    if status == "invalid_exit_code" or (decision == "stop_success" and status in EVIDENCE_GAP_STATUSES):
        errors.append(f"unresolved evidence status: {status}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a short Harness cycle log entry.")
    parser.add_argument("title", help="Cycle title.")
    parser.add_argument("--changed", action="append", default=[], help="What changed. Can be repeated.")
    parser.add_argument("--verified", action="append", default=[], help="What was verified. Can be repeated.")
    parser.add_argument("--remaining", action="append", default=[], help="Remaining work or risk. Can be repeated.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--date", default="", help="Cycle date as YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--task", default="", type=validate_task_id, help="Task ID. Writes to cycles/<task-id>.md and is recommended for parallel work.")
    parser.add_argument("--worker", default="", help="Agent or worker name recorded in the entry.")
    parser.add_argument("--cycle-number", type=int, default=None, help="Cycle number. Defaults to the next entry number for the selected file.")
    parser.add_argument("--max-cycles", type=int, default=None, help="Optional cycle budget recorded as N/max.")
    parser.add_argument(
        "--budget-mode",
        choices=sorted(VALID_BUDGET_MODES),
        default="",
        help="Whether the recorded budget is an exact count or an upper bound. Defaults to exact_count with --max-cycles.",
    )
    parser.add_argument("--decision", choices=["continue", "stop_success", "stop_blocked"], default="", help="Decision at the end of this cycle.")
    parser.add_argument("--success-criterion", action="append", default=[], help="Success criterion this cycle is working toward. Can be repeated.")
    parser.add_argument("--claim", action="append", default=[], help="Claim supported by this cycle's evidence. Can be repeated.")
    parser.add_argument("--evidence-kind", action="append", choices=sorted(EVIDENCE_KINDS), default=[], help="Evidence layer. Can be repeated.")
    parser.add_argument("--evidence-command", action="append", default=[], help="Command or observation that produced evidence. Can be repeated.")
    parser.add_argument("--evidence-exit-code", action="append", default=[], help="Exit code paired with evidence. Can be repeated.")
    parser.add_argument("--artifact", action="append", default=[], help="Evidence artifact path or stable reference. Can be repeated.")
    parser.add_argument("--input-revision", default="", help="Revision/hash of the input under test.")
    parser.add_argument("--artifact-revision", default="", help="Input revision represented by the artifact.")
    parser.add_argument("--scope", action="append", default=[], help="Acceptance scope. Can be repeated.")
    parser.add_argument("--acceptance", choices=sorted(ACCEPTANCE_VALUES), default="", help="Acceptance result for the declared scope.")
    parser.add_argument("--supersedes", action="append", default=[], help="Older section/reference replaced by this entry. Can be repeated.")
    parser.add_argument("--invalidated", action="store_true", help="Mark this entry's claims as invalidated while preserving history.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--write", action="store_true", help="Append to the selected Harness/work/cycles file.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    path = today_cycle_path(root)
    if args.task:
        path = cycles_dir(root) / f"{args.task}.md"
    if args.date:
        if args.task:
            parser.error("--date and --task cannot be used together")
        try:
            path = cycles_dir(root) / f"{parse_date_text(args.date)}.md"
        except ValueError:
            parser.error("--date must be in YYYY-MM-DD format")

    cycle_number = args.cycle_number
    if cycle_number is None and (args.task or args.max_cycles is not None or args.decision):
        cycle_number = entry_count(path) + 1
    if args.max_cycles is not None and args.max_cycles < 1:
        parser.error("--max-cycles must be at least 1")
    if cycle_number is not None and cycle_number < 1:
        parser.error("--cycle-number must be at least 1")
    if cycle_number is not None and args.max_cycles is not None and cycle_number > args.max_cycles:
        parser.error("--cycle-number cannot exceed --max-cycles")
    budget_mode = args.budget_mode
    if budget_mode and args.max_cycles is None:
        parser.error("--budget-mode requires --max-cycles")
    if args.max_cycles is not None and not budget_mode:
        budget_mode = "exact_count"
    iteration_errors = validate_iteration_entry(
        path,
        cycle_number,
        args.max_cycles,
        args.decision,
        budget_mode=budget_mode,
        evidence_kinds=args.evidence_kind,
        artifacts=args.artifact,
        input_revision=args.input_revision,
        artifact_revision=args.artifact_revision,
        acceptance=args.acceptance,
        invalidated=args.invalidated,
        evidence_exit_codes=args.evidence_exit_code,
    )
    if iteration_errors:
        parser.error("; ".join(iteration_errors))
    entry = build_entry(
        args.title,
        args.changed,
        args.verified,
        args.remaining,
        args.worker,
        cycle_number=cycle_number,
        max_cycles=args.max_cycles,
        budget_mode=budget_mode,
        decision=args.decision,
        success_criteria=args.success_criterion,
        claims=args.claim,
        evidence_kinds=args.evidence_kind,
        evidence_commands=args.evidence_command,
        evidence_exit_codes=args.evidence_exit_code,
        artifacts=args.artifact,
        input_revision=args.input_revision,
        artifact_revision=args.artifact_revision,
        scopes=args.scope,
        acceptance=args.acceptance,
        supersedes=args.supersedes,
        invalidated=args.invalidated,
    )
    result = {"root": str(root), "path": rel(path, root), "write": args.write, "entry": entry}
    if args.write:
        append_entry(path, entry)
        result["status"] = "written"
    else:
        result["status"] = "dry_run"

    if args.json:
        print(dump_json(result))
    elif args.write:
        print(f"Appended cycle entry: {path}")
    else:
        print(entry.rstrip())
        print(f"\nDry run only. Add --write to append to {path}")


if __name__ == "__main__":
    main()
