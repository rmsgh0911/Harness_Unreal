"""Scan long-lived Harness text for sensitive values without echoing matches."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, load_json, rel


ALLOWLIST_PATH = Path("Harness/config/sensitive_allowlist.json")
MAX_TEXT_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".toml", ".txt", ".yaml", ".yml"}
ROOT_TEXT_FILES = ("AGENTS.md", "CLAUDE.md", "HARNESS.md", "README.md")
HARNESS_TEXT_FILES = ("Harness/Progress.md", "Harness/template.lock.json")
SCAN_DIRECTORIES = (
    "Harness/config",
    "Harness/docs",
    "Harness/index",
    "Harness/work",
    "Harness/data/memory",
)

HIGH_CONFIDENCE_RULES = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----", re.IGNORECASE),
    ),
    (
        "url_userinfo",
        re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s/]+", re.IGNORECASE),
    ),
    (
        "github_token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?:[\"'])?(?:password|passwd|pwd|client_secret|api_key|access_token|refresh_token|secret)(?:[\"'])?"
    r"\s*[:=]\s*(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;#}\]]+)"
)
PLACEHOLDER_MARKERS = (
    "${",
    "{{",
    "<",
    "changeme",
    "dummy",
    "example",
    "placeholder",
    "redacted",
    "replace_me",
    "replace-with",
    "todo",
    "your_",
)


def normalize_line(line: str) -> str:
    """Normalize spacing before hashing an allowlisted line."""
    return re.sub(r"\s+", " ", line.strip())


def normalized_line_sha256(line: str) -> str:
    return hashlib.sha256(normalize_line(line).encode("utf-8")).hexdigest()


def _finding(path: str, line: int, rule_id: str, severity: str) -> dict:
    return {"path": path, "line": line, "rule_id": rule_id, "severity": severity}


def _placeholder(value: str) -> bool:
    candidate = value.strip().strip("\"'").casefold()
    if len(candidate) < 8:
        return True
    if candidate and set(candidate) <= {"*", "x", "-", "_"}:
        return True
    if candidate.startswith(("env:", "os.environ", "process.env", "%")):
        return True
    return any(marker in candidate for marker in PLACEHOLDER_MARKERS)


def _iter_scan_files(root: Path) -> list[Path]:
    candidates: set[Path] = set()
    for relative in (*ROOT_TEXT_FILES, *HARNESS_TEXT_FILES):
        path = root / relative
        if path.is_file() or path.is_symlink():
            candidates.add(path)
    for relative in SCAN_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in directory.rglob("*"):
            if (path.is_file() or path.is_symlink()) and path.suffix.casefold() in TEXT_SUFFIXES:
                candidates.add(path)
    return sorted(candidates, key=lambda path: rel(path, root).casefold())


def _load_allowlist(root: Path) -> tuple[set[tuple[str, str, str]], list[dict]]:
    path = root / ALLOWLIST_PATH
    relative = ALLOWLIST_PATH.as_posix()
    if not path.exists():
        # Receipt-free/older Harness installs remain scannable; the template
        # ships the file, but absence means there are simply no exceptions.
        return set(), []
    try:
        data = load_json(path, {})
    except (OSError, ValueError, TypeError):
        return set(), [_finding(relative, 0, "allowlist_invalid", "error")]
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        return set(), [_finding(relative, 0, "allowlist_invalid", "error")]

    allowed: set[tuple[str, str, str]] = set()
    issues: list[dict] = []
    for entry in data["entries"]:
        if not isinstance(entry, dict):
            issues.append(_finding(relative, 0, "allowlist_invalid_entry", "error"))
            continue
        entry_path = entry.get("path")
        rule_id = entry.get("rule_id")
        line_hash = entry.get("line_sha256")
        reason = entry.get("reason")
        expires = entry.get("expires")
        if not all(isinstance(value, str) and value.strip() for value in (entry_path, rule_id, line_hash, reason, expires)):
            issues.append(_finding(relative, 0, "allowlist_invalid_entry", "error"))
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", line_hash):
            issues.append(_finding(relative, 0, "allowlist_invalid_hash", "error"))
            continue
        try:
            expiry = date.fromisoformat(expires)
        except ValueError:
            issues.append(_finding(relative, 0, "allowlist_invalid_expiry", "error"))
            continue
        normalized_path = Path(entry_path).as_posix().lstrip("/")
        if expiry < date.today():
            issues.append(_finding(normalized_path, 0, "allowlist_expired", "warning"))
            continue
        allowed.add((normalized_path, rule_id, line_hash))
    return allowed, issues


def build_report(root: Path, strict: bool = False) -> dict:
    allowed, findings = _load_allowlist(root)
    scanned: list[str] = []
    allowlisted_count = 0

    for path in _iter_scan_files(root):
        relative = rel(path, root)
        if path.is_symlink():
            findings.append(_finding(relative, 0, "symlink_not_scanned", "warning"))
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                findings.append(_finding(relative, 0, "text_file_too_large", "warning"))
                continue
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            findings.append(_finding(relative, 0, "text_unreadable", "warning"))
            continue
        scanned.append(relative)
        for line_number, line in enumerate(text.splitlines(), start=1):
            line_hash = normalized_line_sha256(line)
            line_findings: list[tuple[str, str]] = []
            for rule_id, pattern in HIGH_CONFIDENCE_RULES:
                if pattern.search(line):
                    line_findings.append((rule_id, "error"))
            for match in ASSIGNMENT_PATTERN.finditer(line):
                if not _placeholder(match.group("value")):
                    line_findings.append(("credential_assignment", "warning"))
            for rule_id, severity in sorted(set(line_findings)):
                if (relative, rule_id, line_hash) in allowed:
                    allowlisted_count += 1
                    continue
                findings.append(_finding(relative, line_number, rule_id, severity))

    findings.sort(key=lambda item: (item["path"].casefold(), item["line"], item["rule_id"]))
    blocking = [item for item in findings if item["severity"] == "error" or strict]
    return {
        "root": str(root),
        "ok": not blocking,
        "strict": strict,
        "scanned_files": scanned,
        "allowlisted_count": allowlisted_count,
        "findings": findings,
        "summary": {
            "files": len(scanned),
            "errors": sum(item["severity"] == "error" for item in findings),
            "warnings": sum(item["severity"] == "warning" for item in findings),
            "blocking": len(blocking),
        },
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Sensitive Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Strict: {report['strict']}",
        f"- Files: {report['summary']['files']}",
        f"- Errors: {report['summary']['errors']}",
        f"- Warnings: {report['summary']['warnings']}",
        f"- Allowlisted: {report['allowlisted_count']}",
    ]
    if report["findings"]:
        lines.extend(["", "Findings (matched values are intentionally omitted):"])
        lines.extend(
            f"- {item['path']}:{item['line']}: {item['rule_id']} ({item['severity']})"
            for item in report["findings"]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan long-lived Harness text without printing matched sensitive values.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--strict", action="store_true", help="Treat ambiguous warnings as blockers.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON without matched values.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, strict=args.strict)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
