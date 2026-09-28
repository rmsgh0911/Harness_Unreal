"""Tests for generated-artifact provenance validation."""

import hashlib

from _harness_test_base import *  # noqa: F401,F403

from harness_artifact_check import build_report as build_artifact_report


class ArtifactCheckTests(HarnessBaseTestCase):
    def write_registry(self, artifacts: list[dict]) -> None:
        (self.root / "Harness/config/generated_artifacts.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": artifacts}),
            encoding="utf-8",
        )

    def valid_entry(self) -> dict:
        source = self.root / "Source/UI/Dashboard.cpp"
        output = self.root / "Saved/Reports/dashboard.json"
        output.parent.mkdir(parents=True)
        output.write_text('{"ok": true}\n', encoding="utf-8")
        return {
            "id": "dashboard-runtime",
            "generator": "Harness/scripts/project/build_dashboard.py",
            "generator_revision": "tool-v2",
            "generated_at": "2026-09-23T18:00:00+09:00",
            "input_revision": "abc123",
            "artifact_revision": "abc123",
            "source_paths": [source.relative_to(self.root).as_posix()],
            "output": output.relative_to(self.root).as_posix(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "evidence_kind": "runtime",
            "scope": "dashboard data generation",
            "acceptance": "passed",
            "verify_command": "python verify_dashboard.py",
        }

    def test_empty_registry_and_missing_registry_are_compatible(self) -> None:
        self.write_registry([])
        self.assertTrue(build_artifact_report(self.root)["ok"])
        (self.root / "Harness/config/generated_artifacts.json").unlink()
        report = build_artifact_report(self.root)
        self.assertTrue(report["ok"])
        self.assertEqual("not_configured", report["status"])

    def test_valid_entry_checks_output_hash_and_revision(self) -> None:
        self.write_registry([self.valid_entry()])
        report = build_artifact_report(self.root, strict=True)
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["summary"]["entries"])

    def test_unsafe_path_revision_mismatch_and_missing_output_fail(self) -> None:
        entry = self.valid_entry()
        entry["output"] = "../outside.json"
        entry["artifact_revision"] = "stale"
        self.write_registry([entry])
        report = build_artifact_report(self.root)
        fields = {item["field"] for item in report["errors"]}
        self.assertFalse(report["ok"])
        self.assertIn("output", fields)
        self.assertIn("artifact_revision", fields)

    def test_dot_output_is_rejected_without_crashing(self) -> None:
        entry = self.valid_entry()
        entry["output"] = "."
        self.write_registry([entry])
        report = build_artifact_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["field"] == "output" for item in report["errors"]))

    def test_control_character_path_is_rejected_without_crashing(self) -> None:
        entry = self.valid_entry()
        entry["output"] = "Saved/Reports/bad\u0000name.json"
        self.write_registry([entry])
        report = build_artifact_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["field"] == "output" for item in report["errors"]))

    def test_hash_mismatch_fails_without_printing_file_content(self) -> None:
        entry = self.valid_entry()
        entry["output_sha256"] = "0" * 64
        self.write_registry([entry])
        report = build_artifact_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["message"] == "hash_mismatch" for item in report["errors"]))
        self.assertNotIn('{"ok": true}', json.dumps(report))

    def test_pending_acceptance_is_warning_and_strict_blocker(self) -> None:
        entry = self.valid_entry()
        entry["acceptance"] = "pending"
        self.write_registry([entry])
        self.assertTrue(build_artifact_report(self.root, strict=False)["ok"])
        strict = build_artifact_report(self.root, strict=True)
        self.assertFalse(strict["ok"])
        self.assertTrue(any(item["message"] == "not_passed:pending" for item in strict["warnings"]))
