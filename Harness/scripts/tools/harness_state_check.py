"""Check Harness state/next/cycle documents for bloat and stale structure."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import cycles_dir, dump_json, find_project_root, harness_dir, launcher_command, load_json, next_path, read_text, rel, state_path, tasks_dir


HISTORY_HINTS = [
    "On 20",
    "migrated",
    "migration",
    "이식",
    "제거",
    "추가했다",
    "변경:",
    "검증:",
    "남은 것:",
]
_DATE_PATTERN = re.compile(r"20\d\d-\d\d-\d\d")
_CONSOLIDATED_PATTERN = re.compile(r"Last consolidated:\s*(20\d\d-\d\d-\d\d)", re.IGNORECASE)
_COMPLETED_CHECKBOX_PATTERN = re.compile(r"^\s*-\s*\[[xX]\]", re.MULTILINE)
# Mirrors harness_archive.COMPLETED_STATUS_PATTERN so the warning matches what the archive tool accepts.
_COMPLETED_TASK_STATUS_PATTERN = re.compile(r"^\s*-\s*Status:\s*(completed|complete|done|closed)\s*$", re.IGNORECASE | re.MULTILINE)
_TOP_LEVEL_BULLET_PATTERN = re.compile(r"^-\s+", re.MULTILINE)
STATE_ALLOWED_SECTIONS = ["Project", "Current State", "Latest Verification", "Risks"]
NEXT_HISTORY_HEADINGS = ["complete", "completed", "done", "history", "archive", "완료", "이력", "과거"]
SUSPICIOUS_ENCODING_MARKERS = ["\ufffd", "â€", "ì„", "ë¬", "ê°"]
UNRESOLVED_HINTS = ["작성 필요", "TODO", "TBD"]
OLD_PATH_HINTS = [
    "Harness/scripts/verify_project.py",
    "Harness/scripts/create_level.py",
    "Harness/scripts/build_verify.ps1",
    "Harness/scripts/build_verify.cmd",
]
FINDING_CATEGORIES = [
    ("longer_than_soft_limit", "document.soft_limit"),
    ("longer_than_hard_limit", "document.hard_limit"),
    ("unresolved_placeholders", "document.placeholders"),
    ("old_script_paths", "document.old_paths"),
    ("appears to contain work-log", "state.work_log"),
    ("unexpected current-state sections", "state.unexpected_sections"),
    ("missing recommended sections", "state.missing_sections"),
    ("Last consolidated is", "state.stale_consolidation"),
    ("completed checklist items", "next.completed_items"),
    ("history-like headings", "next.history_headings"),
    ("too many active project items", "next.item_count"),
    ("large cycle files", "cycles.large_files"),
    ("many cycle files", "cycles.file_count"),
    ("large cycle history", "cycles.total_lines"),
    ("completed task records", "tasks.completed_records"),
    ("large task files", "tasks.large_files"),
    ("many task files", "tasks.file_count"),
    ("duplicate current-document bullet", "current.duplicate_fact"),
    ("mojibake", "current.encoding"),
]


def stable_finding_id(item: dict) -> str:
    path_key = re.sub(r"[^a-z0-9]+", ".", item.get("path", "unknown").casefold()).strip(".")
    message = item.get("message", "")
    category = next((value for hint, value in FINDING_CATEGORIES if hint in message), "other")
    return f"{path_key}:{category}"


def load_record_policy(root: Path) -> dict:
    path = harness_dir(root) / "config" / "record_policy.json"
    result = {"path": rel(path, root), "exists": path.exists(), "entries": {}, "errors": []}
    if not path.exists():
        return result
    try:
        value = load_json(path, {})
    except (OSError, ValueError) as exc:
        result["errors"].append(f"record policy is unreadable: {exc}")
        return result
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        result["errors"].append("record policy must be an object with schema_version 1")
        return result
    baseline = value.get("warning_baseline", [])
    if not isinstance(baseline, list):
        result["errors"].append("record policy warning_baseline must be a list")
        return result
    for index, entry in enumerate(baseline):
        if not isinstance(entry, dict):
            result["errors"].append(f"warning_baseline[{index}] must be an object")
            continue
        finding_id = str(entry.get("id", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        expires = str(entry.get("expires", "")).strip()
        if not finding_id or not reason or not expires:
            result["errors"].append(f"warning_baseline[{index}] requires id, reason, and expires")
            continue
        try:
            expiry = datetime.strptime(expires, "%Y-%m-%d").date()
        except ValueError:
            result["errors"].append(f"warning_baseline[{index}] expires must use YYYY-MM-DD")
            continue
        if finding_id in result["entries"]:
            result["errors"].append(f"duplicate warning baseline id: {finding_id}")
            continue
        result["entries"][finding_id] = {"reason": reason, "expires": expires, "expired": expiry < date.today()}
    return result


def classify_warning_debt(findings: list[dict], policy: dict) -> dict:
    active_ids: set[str] = set()
    for item in findings:
        item["id"] = stable_finding_id(item)
        if item.get("level") != "warning":
            item["debt_status"] = "not_applicable"
            continue
        active_ids.add(item["id"])
        baseline = policy["entries"].get(item["id"])
        if not baseline:
            item["debt_status"] = "new"
        elif baseline["expired"]:
            item["debt_status"] = "expired"
            item["baseline"] = baseline
        else:
            item["debt_status"] = "baseline"
            item["baseline"] = baseline
    return {
        "new": sorted(item["id"] for item in findings if item.get("debt_status") == "new"),
        "expired": sorted(item["id"] for item in findings if item.get("debt_status") == "expired"),
        "baseline": sorted(item["id"] for item in findings if item.get("debt_status") == "baseline"),
        "resolved": sorted(set(policy["entries"]) - active_ids),
    }


def line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def count_hits(text: str, hints: list[str]) -> int:
    return sum(text.count(hint) for hint in hints)


def is_template_unconfigured(root: Path) -> bool:
    project = load_json(harness_dir(root) / "config" / "project.json", {}) or {}
    if isinstance(project, dict) and project.get("template_mode"):
        return True
    project_configured = bool(project.get("project_name") and project.get("uproject_file")) if isinstance(project, dict) else False
    return not project_configured and not list(root.glob("*.uproject"))


def check_file(root: Path, relative: str, soft_limit: int, hard_limit: int, allow_placeholders: bool = False) -> dict:
    path = root / relative
    text = read_text(path)
    lines = line_count(text)
    warnings: list[str] = []
    errors: list[str] = []
    if not path.exists():
        warnings.append("missing")
    if lines > soft_limit:
        warnings.append(f"longer_than_soft_limit:{soft_limit}")
    if lines > hard_limit:
        errors.append(f"longer_than_hard_limit:{hard_limit}")
    unresolved = count_hits(text, UNRESOLVED_HINTS)
    old_paths = count_hits(text, OLD_PATH_HINTS)
    if unresolved and not allow_placeholders:
        warnings.append(f"unresolved_placeholders:{unresolved}")
    if old_paths:
        warnings.append(f"old_script_paths:{old_paths}")
    return {
        "path": relative,
        "exists": path.exists(),
        "lines": lines,
        "chars": len(text),
        "warnings": warnings,
        "errors": errors,
    }


def state_specific(root: Path) -> dict:
    relative = "Harness/work/state.md"
    text = read_text(state_path(root))
    history_hits = count_hits(text, HISTORY_HINTS) + len(_DATE_PATTERN.findall(text))
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    consolidated_age_days = None
    consolidated_line = None
    consolidated_match = _CONSOLIDATED_PATTERN.search(text)
    if consolidated_match:
        consolidated_line = text[:consolidated_match.start()].count("\n") + 1
        try:
            consolidated_age_days = (date.today() - datetime.strptime(consolidated_match.group(1), "%Y-%m-%d").date()).days
        except ValueError:
            consolidated_age_days = None
    return {
        "path": relative,
        "history_hint_count": history_hits,
        "looks_like_work_log": history_hits >= 8,
        "sections": headings,
        "unexpected_sections": [heading for heading in headings if heading not in STATE_ALLOWED_SECTIONS],
        "missing_sections": [heading for heading in STATE_ALLOWED_SECTIONS if heading not in headings],
        "consolidated_age_days": consolidated_age_days,
        "consolidated_line": consolidated_line,
    }


def next_specific(root: Path) -> dict:
    relative = "Harness/work/next.md"
    text = read_text(next_path(root))
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    history_headings = [heading for heading in headings if any(hint in heading.lower() for hint in NEXT_HISTORY_HEADINGS)]
    completed_lines = [number for number, line in enumerate(text.splitlines(), start=1) if _COMPLETED_CHECKBOX_PATTERN.match(line)]
    history_heading_lines = [number for number, line in enumerate(text.splitlines(), start=1) if line.startswith("## ") and line[3:].strip() in history_headings]
    return {
        "path": relative,
        "active_item_count": len(_TOP_LEVEL_BULLET_PATTERN.findall(text)),
        "completed_checkbox_count": len(_COMPLETED_CHECKBOX_PATTERN.findall(text)),
        "completed_lines": completed_lines,
        "history_headings": history_headings,
        "history_heading_lines": history_heading_lines,
    }


def current_doc_quality(root: Path) -> list[dict]:
    paths = [state_path(root), next_path(root), harness_dir(root) / "Progress.md"]
    findings: list[dict] = []
    bullets: dict[str, list[tuple[str, int]]] = {}
    for path in paths:
        relative = rel(path, root)
        for line_number, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("- "):
                normalized = re.sub(r"\s+", " ", stripped[2:].strip()).casefold()
                if len(normalized) >= 20 and "todo" not in normalized and "작성 필요" not in normalized:
                    bullets.setdefault(normalized, []).append((relative, line_number))
            if any(marker in line for marker in SUSPICIOUS_ENCODING_MARKERS):
                findings.append({
                    "level": "warning",
                    "path": relative,
                    "line": line_number,
                    "message": "suspicious UTF-8/mojibake marker; re-read and save the file as UTF-8",
                })
    for locations in bullets.values():
        if len({path for path, _ in locations}) > 1:
            rendered = ", ".join(f"{path}:{line}" for path, line in locations)
            findings.append({
                "level": "warning",
                "path": locations[0][0],
                "line": locations[0][1],
                "message": f"duplicate current-document bullet; keep one source of truth ({rendered})",
            })
    return findings


def cycle_summary(root: Path) -> dict:
    cycles = cycles_dir(root)
    files = sorted(path for path in cycles.glob("*.md") if path.name != ".gitkeep") if cycles.exists() else []
    large_files: list[dict] = []
    total_lines = 0
    for path in files:
        text = read_text(path)
        lines = line_count(text)
        total_lines += lines
        if lines > 250:
            large_files.append({"path": rel(path, root), "lines": lines})
    return {
        "file_count": len(files),
        "total_lines": total_lines,
        "large_files": large_files,
    }


def task_summary(root: Path) -> dict:
    tasks = tasks_dir(root)
    excluded = {"README.md", "task.example.md"}
    files = sorted(path for path in tasks.glob("*.md") if path.name not in excluded) if tasks.exists() else []
    large_files: list[dict] = []
    completed_tasks: list[str] = []
    total_lines = 0
    for path in files:
        text = read_text(path)
        lines = line_count(text)
        total_lines += lines
        if lines > 180:
            large_files.append({"path": rel(path, root), "lines": lines})
        if _COMPLETED_TASK_STATUS_PATTERN.search(text):
            completed_tasks.append(path.stem)
    return {
        "file_count": len(files),
        "total_lines": total_lines,
        "large_files": large_files,
        "completed_tasks": completed_tasks,
    }


def build_report(root: Path, strict: bool = False) -> dict:
    template_unconfigured = is_template_unconfigured(root)
    docs = [
        check_file(root, "Harness/work/state.md", soft_limit=80, hard_limit=220, allow_placeholders=template_unconfigured),
        check_file(root, "Harness/work/next.md", soft_limit=60, hard_limit=100, allow_placeholders=template_unconfigured),
        check_file(root, "Harness/README.md", soft_limit=160, hard_limit=260),
    ]
    state = state_specific(root)
    next_doc = next_specific(root)
    cycles = cycle_summary(root)
    tasks = task_summary(root)
    findings: list[dict] = []
    for doc in docs:
        for error in doc["errors"]:
            findings.append({"level": "error", "path": doc["path"], "message": error})
        for warning in doc["warnings"]:
            findings.append({"level": "warning", "path": doc["path"], "message": warning})
    if state["looks_like_work_log"]:
        findings.append({"level": "warning", "path": state["path"], "message": "state.md appears to contain work-log or migration history"})
    if state["unexpected_sections"]:
        findings.append({"level": "warning", "path": state["path"], "message": "unexpected current-state sections: " + ", ".join(state["unexpected_sections"])})
    if state["missing_sections"]:
        findings.append({"level": "warning", "path": state["path"], "message": "missing recommended sections: " + ", ".join(state["missing_sections"])})
    if state["consolidated_age_days"] is not None and state["consolidated_age_days"] > 30:
        findings.append({"level": "warning", "path": state["path"], "line": state["consolidated_line"], "message": f"Last consolidated is {state['consolidated_age_days']} days old; confirm and refresh the snapshot before relying on it"})
    if next_doc["completed_checkbox_count"]:
        findings.append({"level": "warning", "path": next_doc["path"], "line": next_doc["completed_lines"][0], "message": f"completed checklist items should be removed or archived: {next_doc['completed_checkbox_count']}"})
    if next_doc["history_headings"]:
        findings.append({"level": "warning", "path": next_doc["path"], "line": next_doc["history_heading_lines"][0], "message": "history-like headings should move to task/cycle records or an archive: " + ", ".join(next_doc["history_headings"])})
    if next_doc["active_item_count"] > 5:
        findings.append({"level": "warning", "path": next_doc["path"], "message": f"too many active project items: {next_doc['active_item_count']} > 5"})
    archive_hint = f"archive old date cycles: {launcher_command('archive --before YYYY-MM --archive')}"
    if cycles["large_files"]:
        findings.append({"level": "info", "path": "Harness/work/cycles/", "message": f"large cycle files: {len(cycles['large_files'])}"})
    if cycles["file_count"] > 45:
        findings.append({"level": "info", "path": "Harness/work/cycles/", "message": f"many cycle files: {cycles['file_count']} ({archive_hint})"})
    if cycles["total_lines"] > 1200:
        findings.append({"level": "info", "path": "Harness/work/cycles/", "message": f"large cycle history: {cycles['total_lines']} lines ({archive_hint})"})
    if tasks["completed_tasks"]:
        findings.append({
            "level": "warning",
            "path": "Harness/work/tasks/",
            "message": f"completed task records should be archived ({launcher_command('archive --task <id> --archive')}): "
            + ", ".join(tasks["completed_tasks"]),
        })
    if tasks["large_files"]:
        findings.append({"level": "warning", "path": "Harness/work/tasks/", "message": f"large task files: {len(tasks['large_files'])}"})
    if tasks["file_count"] > 50:
        findings.append({"level": "info", "path": "Harness/work/tasks/", "message": f"many task files: {tasks['file_count']}"})
    findings.extend(current_doc_quality(root))
    policy = load_record_policy(root)
    for error in policy["errors"]:
        findings.append({"level": "error", "path": policy["path"], "message": error})
    warning_debt = classify_warning_debt(findings, policy)
    blocking_debt = bool(warning_debt["new"] or warning_debt["expired"])
    return {
        "root": str(root),
        "ok": not any(item["level"] == "error" for item in findings) and not (strict and blocking_debt),
        "strict": strict,
        "template_unconfigured": template_unconfigured,
        "docs": docs,
        "state": state,
        "next": next_doc,
        "cycles": cycles,
        "tasks": tasks,
        "record_policy": {"path": policy["path"], "exists": policy["exists"], "errors": policy["errors"]},
        "warning_debt": warning_debt,
        "findings": findings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness State Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Strict warning debt: {'on' if report['strict'] else 'off'}",
        f"- Work cycle files: {report['cycles']['file_count']}",
        f"- Work cycle total lines: {report['cycles']['total_lines']}",
        f"- Task files: {report['tasks']['file_count']}",
    ]
    lines.append("")
    lines.append("Docs:")
    for doc in report["docs"]:
        warn = ", ".join(doc["warnings"]) if doc["warnings"] else "ok"
        lines.append(f"- {doc['path']}: {doc['lines']} lines, {warn}")
    if report["findings"]:
        lines.append("")
        lines.append("Findings:")
        lines.extend(
            f"- [{item['level']}/{item.get('debt_status', 'not_applicable')}] {item['id']} {item['path']}{':' + str(item['line']) if item.get('line') else ''}: {item['message']}"
            for item in report["findings"]
        )
    if report["warning_debt"]["resolved"]:
        lines.extend(["", "Resolved baseline IDs:", *(f"- {item}" for item in report["warning_debt"]["resolved"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Harness state, next, and cycle documents for bloat, stale paths, and misplaced history.")
    parser.add_argument("--target", type=Path, default=None, help="Target project root. Defaults to nearest Harness root.")
    parser.add_argument("--strict", action="store_true", help="Fail on warning IDs that are new or whose baseline entry expired.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = args.target.resolve() if args.target else find_project_root()
    report = build_report(root, strict=args.strict)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
