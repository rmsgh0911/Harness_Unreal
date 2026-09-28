"""Validate project-owned provenance records for generated evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, load_json, rel


REGISTRY_RELATIVE = "Harness/config/generated_artifacts.json"
EVIDENCE_KINDS = {"structure", "runtime", "render", "interaction", "live_service"}
ACCEPTANCE_VALUES = {"passed", "pending", "failed", "skipped", "not_required"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("\\", "/")
    if any(ord(character) < 32 for character in normalized):
        return None
    candidate = PurePosixPath(normalized)
    if not candidate.parts or candidate.is_absolute() or candidate.parts[0].endswith(":") or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    return candidate.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contained_path(root: Path, relative: str) -> Path | None:
    try:
        root_resolved = root.resolve()
        candidate = (root / relative).resolve(strict=False)
        if not candidate.is_relative_to(root_resolved):
            return None
        return candidate
    except (OSError, ValueError):
        return None


def _timestamp_has_timezone(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def build_report(root: Path, strict: bool = False) -> dict:
    registry_path = root / REGISTRY_RELATIVE
    errors: list[dict] = []
    warnings: list[dict] = []
    entries: list[dict] = []
    if not registry_path.exists():
        return {
            "root": str(root),
            "registry": REGISTRY_RELATIVE,
            "status": "not_configured",
            "strict": strict,
            "ok": True,
            "summary": {"entries": 0, "errors": 0, "warnings": 0},
            "entries": [],
            "errors": [],
            "warnings": [],
        }
    try:
        registry = load_json(registry_path, {})
    except (OSError, ValueError) as exc:
        errors.append({"id": "registry", "field": "file", "message": f"unreadable_json:{type(exc).__name__}"})
        registry = {}
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        errors.append({"id": "registry", "field": "schema_version", "message": "must_equal_1"})
    raw_entries = registry.get("artifacts", []) if isinstance(registry, dict) else []
    if not isinstance(raw_entries, list):
        errors.append({"id": "registry", "field": "artifacts", "message": "must_be_list"})
        raw_entries = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_entries):
        entry_id = f"entry_{index}"
        entry_errors: list[dict] = []
        entry_warnings: list[dict] = []
        if not isinstance(raw, dict):
            errors.append({"id": entry_id, "field": "entry", "message": "must_be_object"})
            continue
        requested_id = str(raw.get("id", "")).strip()
        if not ID_PATTERN.fullmatch(requested_id):
            entry_errors.append({"id": entry_id, "field": "id", "message": "invalid_id"})
        else:
            entry_id = requested_id
            if entry_id in seen_ids:
                entry_errors.append({"id": entry_id, "field": "id", "message": "duplicate_id"})
            seen_ids.add(entry_id)
        output_relative = safe_relative_path(raw.get("output"))
        if output_relative is None:
            entry_errors.append({"id": entry_id, "field": "output", "message": "must_be_safe_project_relative_path"})
        digest = str(raw.get("output_sha256", "")).strip().casefold()
        if not SHA256_PATTERN.fullmatch(digest):
            entry_errors.append({"id": entry_id, "field": "output_sha256", "message": "must_be_lowercase_sha256"})
        input_revision = str(raw.get("input_revision", "")).strip()
        artifact_revision = str(raw.get("artifact_revision", "")).strip()
        if not input_revision:
            entry_errors.append({"id": entry_id, "field": "input_revision", "message": "required"})
        if not artifact_revision:
            entry_errors.append({"id": entry_id, "field": "artifact_revision", "message": "required"})
        if input_revision and artifact_revision and input_revision != artifact_revision:
            entry_errors.append({"id": entry_id, "field": "artifact_revision", "message": "does_not_match_input_revision"})
        if not str(raw.get("generator", "")).strip():
            entry_errors.append({"id": entry_id, "field": "generator", "message": "required"})
        if not str(raw.get("generator_revision", "")).strip():
            entry_errors.append({"id": entry_id, "field": "generator_revision", "message": "required"})
        if not str(raw.get("verify_command", "")).strip():
            entry_errors.append({"id": entry_id, "field": "verify_command", "message": "required"})
        if not str(raw.get("scope", "")).strip():
            entry_errors.append({"id": entry_id, "field": "scope", "message": "required"})
        if not _timestamp_has_timezone(raw.get("generated_at")):
            entry_errors.append({"id": entry_id, "field": "generated_at", "message": "must_be_iso8601_with_timezone"})
        evidence_kind = str(raw.get("evidence_kind", "")).strip()
        if evidence_kind not in EVIDENCE_KINDS:
            entry_errors.append({"id": entry_id, "field": "evidence_kind", "message": "unsupported_value"})
        acceptance = str(raw.get("acceptance", "")).strip()
        if acceptance not in ACCEPTANCE_VALUES:
            entry_errors.append({"id": entry_id, "field": "acceptance", "message": "unsupported_value"})
        elif acceptance != "passed":
            entry_warnings.append({"id": entry_id, "field": "acceptance", "message": f"not_passed:{acceptance}"})
        source_paths = raw.get("source_paths", [])
        if not isinstance(source_paths, list) or not source_paths:
            entry_errors.append({"id": entry_id, "field": "source_paths", "message": "non_empty_list_required"})
            source_paths = []
        normalized_sources: list[str] = []
        for source in source_paths:
            normalized = safe_relative_path(source)
            if normalized is None:
                entry_errors.append({"id": entry_id, "field": "source_paths", "message": "contains_unsafe_path"})
                continue
            normalized_sources.append(normalized)
            source_path = contained_path(root, normalized)
            if source_path is None:
                entry_errors.append({"id": entry_id, "field": "source_paths", "message": "path_escapes_project"})
            elif not source_path.exists():
                entry_warnings.append({"id": entry_id, "field": "source_paths", "message": f"source_missing:{normalized}"})
        if output_relative is not None:
            output = contained_path(root, output_relative)
            if output is None:
                entry_errors.append({"id": entry_id, "field": "output", "message": "path_escapes_project"})
            elif not output.is_file():
                entry_errors.append({"id": entry_id, "field": "output", "message": "file_missing"})
            elif SHA256_PATTERN.fullmatch(digest):
                try:
                    actual_digest = file_sha256(output)
                except OSError:
                    entry_errors.append({"id": entry_id, "field": "output", "message": "file_unreadable"})
                else:
                    if actual_digest != digest:
                        entry_errors.append({"id": entry_id, "field": "output_sha256", "message": "hash_mismatch"})
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)
        entries.append(
            {
                "id": entry_id,
                "output": output_relative or "",
                "evidence_kind": evidence_kind,
                "acceptance": acceptance,
                "source_count": len(normalized_sources),
                "ok": not entry_errors and not (strict and entry_warnings),
            }
        )
    return {
        "root": str(root),
        "registry": rel(registry_path, root),
        "status": "checked",
        "strict": strict,
        "ok": not errors and not (strict and warnings),
        "summary": {"entries": len(entries), "errors": len(errors), "warnings": len(warnings)},
        "entries": entries,
        "errors": errors,
        "warnings": warnings,
    }


def format_text(report: dict) -> str:
    lines = [
        "Harness Generated Artifact Check",
        f"- Root: {report['root']}",
        f"- Registry: {report['registry']}",
        f"- Status: {report['status']}",
        f"- Strict: {report['strict']}",
        f"- Entries: {report['summary']['entries']}",
        f"- Errors: {report['summary']['errors']}",
        f"- Warnings: {report['summary']['warnings']}",
    ]
    for title, items in (("Errors", report["errors"]), ("Warnings", report["warnings"])):
        if items:
            lines.extend(["", f"{title}:"])
            lines.extend(f"- {item['id']}:{item['field']}: {item['message']}" for item in items)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated-artifact provenance and output integrity.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--strict", action="store_true", help="Treat pending/failed/skipped acceptance and missing sources as failures.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    report = build_report(find_project_root(args.root), strict=args.strict)
    print(dump_json(report) if args.json else format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
