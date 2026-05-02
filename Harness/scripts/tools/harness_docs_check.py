"""Check ProjectDocs discovery and on-demand read policy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, read_text, rel


REQUEST_READ_HINTS = [
    "기획",
    "GDD",
    "명세",
    "구현기준",
    "체크리스트",
    "시나리오",
    "검증 기준",
    "요구사항",
    "규칙",
    "밸런스",
    "UX",
    "UI",
    "레벨",
    "캐릭터",
    "시뮬레이션",
    "설계",
]
REQUEST_SKIP_HINTS = [
    "컴파일 오류",
    "빌드 오류",
    "포맷",
    "리네임",
    "파일 이동",
]


def add_finding(findings: list[dict], level: str, message: str, path: str = "") -> None:
    item = {"level": level, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def is_safe_relative_path(value: str) -> bool:
    if not value or value.strip() != value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def list_markdown_files(root: Path, doc_roots: list[str]) -> list[str]:
    files: list[str] = []
    for doc_root in doc_roots:
        base = root / doc_root
        if not base.exists() or not base.is_dir():
            continue
        files.extend(rel(path, root) for path in sorted(base.glob("**/*.md")) if path.is_file())
    return files


def configured_hints(docs_config: dict, key: str, fallback: list[str]) -> list[str]:
    request_hints = docs_config.get("request_hints", {})
    if not isinstance(request_hints, dict):
        return fallback
    value = request_hints.get(key, fallback)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        return fallback
    return value


def evaluate_request(request: str, docs_config: dict) -> dict:
    request_text = request.strip()
    if not request_text:
        return {
            "request": "",
            "should_read_docs": False,
            "reason": "no request provided",
            "recommended_first_reads": [],
        }

    read_hints = configured_hints(docs_config, "read", REQUEST_READ_HINTS)
    skip_hints = configured_hints(docs_config, "skip", REQUEST_SKIP_HINTS)
    read_hits = [hint for hint in read_hints if hint.lower() in request_text.lower()]
    skip_hits = [hint for hint in skip_hints if hint.lower() in request_text.lower()]
    should_read = bool(read_hits) and not bool(skip_hits)
    reason = "matched document reference hints" if should_read else "no document read trigger matched"
    if skip_hits:
        reason = "matched skip hints for code-only work"
    return {
        "request": request_text,
        "should_read_docs": should_read,
        "reason": reason,
        "read_hits": read_hits,
        "skip_hits": skip_hits,
        "recommended_first_reads": docs_config.get("entry_points", []) if should_read else [],
    }


def build_report(root: Path, request: str = "") -> dict:
    config_path = harness_dir(root) / "config" / "docs.json"
    findings: list[dict] = []
    docs_config = load_json(config_path, None)
    if not isinstance(docs_config, dict):
        add_finding(findings, "error", "docs.json is missing or is not a JSON object", rel(config_path, root))
        docs_config = {}

    doc_roots = docs_config.get("doc_roots", [])
    entry_points = docs_config.get("entry_points", [])
    read_policy = docs_config.get("read_policy", {})

    if not isinstance(doc_roots, list) or not all(isinstance(item, str) for item in doc_roots):
        add_finding(findings, "error", "doc_roots must be a list of relative paths", rel(config_path, root))
        doc_roots = []
    if not isinstance(entry_points, list) or not all(isinstance(item, str) for item in entry_points):
        add_finding(findings, "error", "entry_points must be a list of relative paths", rel(config_path, root))
        entry_points = []
    if not isinstance(read_policy, dict):
        add_finding(findings, "error", "read_policy must be an object", rel(config_path, root))
        read_policy = {}

    for path_text in [*doc_roots, *entry_points]:
        if not is_safe_relative_path(path_text):
            add_finding(findings, "error", f"path must be safe and relative: {path_text}", rel(config_path, root))

    if not doc_roots:
        add_finding(findings, "warning", "doc_roots is empty; agents cannot discover project documents", rel(config_path, root))
    if not entry_points:
        add_finding(findings, "warning", "entry_points is empty; agents have no first-read document map", rel(config_path, root))

    root_status: list[dict] = []
    for doc_root in doc_roots:
        path = root / doc_root
        inside_harness = path.resolve().parts[: len((root / "Harness").resolve().parts)] == (root / "Harness").resolve().parts
        exists = path.exists() and path.is_dir()
        root_status.append({"path": doc_root, "exists": exists, "inside_harness": inside_harness})
        if not exists:
            add_finding(findings, "warning", "doc root is missing", doc_root)
        if inside_harness:
            add_finding(findings, "error", "project documents must live outside Harness", doc_root)

    entry_status: list[dict] = []
    for entry in entry_points:
        path = root / entry
        exists = path.exists() and path.is_file()
        text = read_text(path)
        has_map_hint = "문서 지도" in text or "Document Map" in text or "README" in path.name
        entry_status.append({"path": entry, "exists": exists, "has_map_hint": has_map_hint})
        if not exists:
            add_finding(findings, "warning", "entry point is missing", entry)
        elif not has_map_hint:
            add_finding(findings, "info", "entry point exists but does not look like a document map", entry)

    if (root / "Harness" / "doc").exists():
        add_finding(findings, "warning", "legacy Harness/doc exists; move project documents to ProjectDocs", "Harness/doc")

    default_policy = read_policy.get("default")
    if default_policy != "on_demand":
        add_finding(findings, "warning", "read_policy.default should be on_demand", rel(config_path, root))
    for key in ["read_when", "do_not_read_when"]:
        value = read_policy.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            add_finding(findings, "warning", f"read_policy.{key} should be a non-empty string list", rel(config_path, root))
    request_hints = docs_config.get("request_hints", {})
    if not isinstance(request_hints, dict):
        add_finding(findings, "warning", "request_hints should be an object with read and skip lists", rel(config_path, root))
    else:
        for key in ["read", "skip"]:
            value = request_hints.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                add_finding(findings, "warning", f"request_hints.{key} should be a non-empty string list", rel(config_path, root))

    markdown_files = list_markdown_files(root, doc_roots)
    request_eval = evaluate_request(request, docs_config)
    errors = [item for item in findings if item["level"] == "error"]
    return {
        "root": str(root),
        "ok": not errors,
        "config": rel(config_path, root),
        "summary": {
            "doc_roots": len(doc_roots),
            "entry_points": len(entry_points),
            "markdown_files": len(markdown_files),
            "findings": len(findings),
        },
        "doc_roots": root_status,
        "entry_points": entry_status,
        "markdown_files": markdown_files,
        "read_policy": {
            "default": default_policy,
            "read_when_count": len(read_policy.get("read_when", [])) if isinstance(read_policy.get("read_when"), list) else 0,
            "do_not_read_when_count": len(read_policy.get("do_not_read_when", [])) if isinstance(read_policy.get("do_not_read_when"), list) else 0,
        },
        "request_hints": {
            "read_count": len(configured_hints(docs_config, "read", REQUEST_READ_HINTS)),
            "skip_count": len(configured_hints(docs_config, "skip", REQUEST_SKIP_HINTS)),
        },
        "request_eval": request_eval,
        "findings": findings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Docs Check",
        f"- Root: {report['root']}",
        f"- Status: {'ok' if report['ok'] else 'needs attention'}",
        f"- Doc roots: {report['summary']['doc_roots']}",
        f"- Entry points: {report['summary']['entry_points']}",
        f"- Markdown files: {report['summary']['markdown_files']}",
        f"- Read policy: {report['read_policy']['default'] or 'missing'}",
    ]
    if report["request_eval"]["request"]:
        request_eval = report["request_eval"]
        lines.append("")
        lines.append("Request policy:")
        lines.append(f"- Should read docs: {request_eval['should_read_docs']}")
        lines.append(f"- Reason: {request_eval['reason']}")
        if request_eval["recommended_first_reads"]:
            lines.append("- First reads:")
            lines.extend(f"  - {path}" for path in request_eval["recommended_first_reads"])
    if report["findings"]:
        lines.append("")
        lines.append("Findings:")
        for item in report["findings"]:
            path = f" {item['path']}:" if item.get("path") else ""
            lines.append(f"- [{item['level']}]{path} {item['message']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check ProjectDocs discovery and docs.json read policy.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Optional user request to evaluate against the docs read policy.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    report = build_report(root, args.request)
    if args.json:
        print(dump_json(report))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
