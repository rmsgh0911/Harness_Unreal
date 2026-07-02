"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class DoctorVerifyTests(HarnessBaseTestCase):
    def test_compile_check_reports_unreadable_source_instead_of_crashing(self) -> None:
        (self.root / "Harness/scripts/tools/sample_tool.py").write_text("VALUE = 1\n", encoding="utf-8")
        with patch("harness_verify_all.py_compile.compile", side_effect=OSError("simulated MAX_PATH overflow")):
            report = compile_python_files(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unreadable source file" in failure["error"] for failure in report["failures"]))
    def test_doctor_flags_unregistered_and_parked_files_in_tools(self) -> None:
        tools = self.root / "Harness/scripts/tools"
        (tools / "tool_manifest.json").write_text('{"tools": []}\n', encoding="utf-8")
        (tools / "one_off_export.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tools / "fbx_combine.cpp").write_text("// stray source\n", encoding="utf-8")
        checks = run_doctor(self.root)["checks"]
        unregistered = [item for item in checks if "not listed in manifest" in item["message"]]
        self.assertTrue(any("one_off_export.py" in item["message"] and not item["ok"] for item in unregistered))
        parked = [item for item in checks if "parked in scripts/tools" in item["message"]]
        self.assertEqual(1, len(parked))
        self.assertFalse(parked[0]["ok"])
        self.assertEqual("warning", parked[0]["severity"])
        self.assertIn("fbx_combine.cpp", parked[0]["message"])
    def test_doctor_warns_when_data_dir_lacks_gitignore_exclusions(self) -> None:
        (self.root / "Harness/data").mkdir()
        (self.root / ".gitignore").write_text("Binaries/\n", encoding="utf-8")
        results = run_doctor(self.root)["checks"]
        matches = [item for item in results if "Harness/data SQLite" in item["message"]]
        self.assertEqual(1, len(matches))
        self.assertFalse(matches[0]["ok"])
        self.assertEqual("warning", matches[0]["severity"])
        (self.root / ".gitignore").write_text("Binaries/\nHarness/data/*.sqlite\n", encoding="utf-8")
        results = run_doctor(self.root)["checks"]
        matches = [item for item in results if "Harness/data SQLite" in item["message"]]
        self.assertTrue(matches[0]["ok"])
    def test_memory_doctor_and_prune_report_quality_candidates(self) -> None:
        memory = self.root / "Harness/data/memory"
        memory.mkdir(parents=True, exist_ok=True)
        stale = (
            '{"id":"00000000-0000-4000-8000-000000000128","created_at":"2020-01-01T12:00:00+09:00",'
            '"status":"draft","title":"Old draft","body":"Remove me after review.","tags":["memory"],"source":""}\n'
        )
        duplicate = (
            '{"id":"00000000-0000-4000-8000-000000000129","created_at":"2026-07-06T12:00:00+09:00",'
            '"status":"confirmed","title":"Same","body":"Same body.","tags":["memory"],"source":""}\n'
            '{"id":"00000000-0000-4000-8000-000000000130","created_at":"2026-07-06T12:01:00+09:00",'
            '"status":"confirmed","title":"Same","body":"Same body.","tags":["memory"],"source":""}\n'
        )
        (memory / "2026-07-06.jsonl").write_text(stale + duplicate, encoding="utf-8")
        doctor = memory_doctor(self.root, draft_days=30, max_body_chars=600)
        kinds = {item["kind"] for item in doctor["findings"]}
        self.assertIn("stale_draft", kinds)
        self.assertIn("duplicate_content", kinds)
        prune_args = argparse.Namespace(write=False, prune_draft_days=30, prune_max_body_chars=600)
        dry_run = prune_memory(self.root, prune_args)
        self.assertEqual(2, len(dry_run["candidates"]))
        prune_args.write = True
        applied = prune_memory(self.root, prune_args)
        self.assertEqual(2, len(applied["removed"]))
    def test_project_build_readiness_is_a_required_verification_gate(self) -> None:
        (self.root / "Harness/config/project.json").write_text(
            '{"template_mode": false, "uproject_file": "", "build": {}}\n',
            encoding="utf-8",
        )
        readiness = check_build_readiness(self.root)
        self.assertFalse(readiness["ok"])
        self.assertFalse(required_checks_ok({"ok": True}, readiness))
