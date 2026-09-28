"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403
from harness_cycle_summary import evidence_status


class CycleTests(HarnessBaseTestCase):
    def test_writer_rejects_failed_exit_codes_for_success_and_keeps_failed_history(self) -> None:
        path = self.root / "Harness/work/cycles/failed.md"
        errors = validate_iteration_entry(path, 1, 2, "stop_success", evidence_kinds=["runtime"], acceptance="passed", evidence_exit_codes=["1"])
        self.assertTrue(any("verification_failed" in error for error in errors))
        self.assertEqual([], validate_iteration_entry(path, 1, 2, "continue", evidence_kinds=["runtime"], acceptance="failed", evidence_exit_codes=["1"]))

    def test_cycle_entry_records_budget_decision_and_success_criteria(self) -> None:
        entry = build_entry(
            "Iteration",
            ["changed"],
            ["verified"],
            ["remaining"],
            worker="Codex",
            cycle_number=3,
            max_cycles=10,
            budget_mode="exact_count",
            decision="continue",
            success_criteria=["repeatable verification"],
        )
        self.assertIn("- Cycle: 3/10", entry)
        self.assertIn("- Budget Mode: exact_count", entry)
        self.assertIn("- Decision: continue", entry)
        self.assertIn("- Success Criteria: repeatable verification", entry)
    def test_cycle_entry_round_trips_optional_evidence_metadata(self) -> None:
        entry = build_entry(
            "Render acceptance",
            ["changed"],
            ["verified"],
            ["none"],
            cycle_number=1,
            max_cycles=2,
            budget_mode="upper_bound",
            decision="continue",
            claims=["Dashboard matches the approved reference"],
            evidence_kinds=["render"],
            evidence_commands=["capture dashboard"],
            evidence_exit_codes=["0"],
            artifacts=["Saved/Acceptance/dashboard.png"],
            input_revision="input-a",
            artifact_revision="input-a",
            scopes=["dashboard layout"],
            acceptance="passed",
            supersedes=["Harness/work/cycles/old.md#Old Render"],
        )
        path = self.root / "Harness/work/cycles/evidence.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(entry, encoding="utf-8")

        section = parse_cycle_file(path)["sections"][0]

        self.assertEqual(["render"], section["evidence_kinds"])
        self.assertEqual("upper_bound", section["budget_mode"])
        self.assertEqual("accepted", section["evidence_status"])
        self.assertEqual("input-a", section["artifact_revision"])
        self.assertEqual(["Harness/work/cycles/old.md#Old Render"], section["supersedes"])

    def test_evidence_status_distinguishes_missing_mismatch_and_skipped(self) -> None:
        base = {"invalidated": False, "evidence_kinds": ["render"], "artifacts": [], "input_revision": "a", "artifact_revision": ""}
        self.assertEqual("missing_artifact", evidence_status({**base, "acceptance": "passed"}))
        self.assertEqual(
            "revision_mismatch",
            evidence_status({**base, "artifacts": ["capture.png"], "artifact_revision": "b", "acceptance": "passed"}),
        )
        self.assertEqual("skipped", evidence_status({**base, "acceptance": "skipped"}))

    def test_stop_success_rejects_unaccepted_render_scope(self) -> None:
        path = self.root / "Harness/work/cycles/evidence.md"
        errors = validate_iteration_entry(
            path,
            cycle_number=1,
            max_cycles=1,
            decision="stop_success",
            evidence_kinds=["render"],
            artifacts=[],
            acceptance="pending",
        )
        self.assertTrue(any("requires passed" in error for error in errors))
    def test_cycle_record_query_does_not_trigger_iteration_mode(self) -> None:
        policy = {"default_max_cycles": 1, "cycle_count_rules": {"phrases": ["cycle", "cycles", "반복"]}}
        self.assertFalse(evaluate_cycle_request("search existing cycle log records", policy)["is_cycle_work"])
        self.assertTrue(evaluate_cycle_request("repeat validation", policy)["is_cycle_work"])
    def test_cycle_summary_parses_structured_iteration_fields(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 Iteration\n\n- Worker: Codex\n- Cycle: 3/10\n- Budget Mode: exact_count\n- Decision: continue\n"
            "- Success Criteria: repeatable verification\n- Changed: tool\n- Verified: unit test\n- Remaining: docs\n",
            encoding="utf-8",
        )
        section = parse_cycle_file(path)["sections"][0]
        self.assertEqual(3, section["cycle_number"])
        self.assertEqual(10, section["max_cycles"])
        self.assertEqual("exact_count", section["budget_mode"])
        self.assertEqual("continue", section["decision"])
        self.assertEqual(["repeatable verification"], section["success_criteria"])
    def test_cycle_summary_reports_invalid_iteration_sequence(self) -> None:
        sections = [
            {"cycle_number": 1, "max_cycles": 5, "decision": "stop_success"},
            {"cycle_number": 3, "max_cycles": 4, "decision": "continue"},
        ]
        status = analyze_iteration(sections)
        self.assertIn("cycle numbers are not a contiguous 1-based sequence", status["warnings"])
        self.assertIn("cycle budget changed within one log", status["warnings"])
        self.assertIn("cycle 1 stops before a later cycle", status["warnings"])
    def test_cycle_summary_reports_only_latest_open_work(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/2\n- Decision: continue\n- Changed: shared\n- Verified: first\n- Remaining: old work\n\n"
            "## 10:10 Two\n- Cycle: 2/2\n- Decision: stop_success\n- Changed: shared\n- Verified: second\n- Remaining: none\n",
            encoding="utf-8",
        )
        summary = build_cycle_summary(self.root, limit=1)
        self.assertEqual("stop_success", summary["latest_decision"])
        self.assertEqual([], summary["open_remaining"])
        self.assertEqual(1, summary["recent_changed"].count("shared"))
    def test_cycle_writer_rejects_continue_at_final_budget(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/2\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        errors = validate_iteration_entry(path, cycle_number=2, max_cycles=2, decision="continue")
        self.assertIn("the final budgeted cycle must use stop_success or stop_blocked", errors)
    def test_cycle_writer_rejects_existing_invalid_sequence(self) -> None:
        path = self.root / "Harness/work/cycles/invalid.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/4\n- Decision: continue\n- Verified: test\n- Remaining: next\n\n"
            "## 10:10 Three\n- Cycle: 3/4\n- Decision: continue\n- Verified: test\n- Remaining: next\n",
            encoding="utf-8",
        )
        errors = validate_iteration_entry(path, cycle_number=3, max_cycles=4, decision="continue")
        self.assertTrue(any("not a contiguous" in error for error in errors))
    def test_cycle_writer_supports_legacy_unnumbered_log(self) -> None:
        path = self.root / "Harness/work/cycles/legacy.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 Old entry\n- Changed: legacy\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        self.assertEqual([], validate_iteration_entry(path, cycle_number=2, max_cycles=None, decision=""))
    def test_iteration_status_stops_on_invalid_cycle_log(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n\n"
            "## 10:10 Three\n- Cycle: 3/3\n- Decision: continue\n- Verified: test\n- Remaining: finish\n",
            encoding="utf-8",
        )
        report = build_iteration_status(self.root, request="3 cycles", task="repeat")
        self.assertIn("cycle numbers are not a contiguous 1-based sequence", report["cycle_log_warnings"])
        self.assertFalse(report["continue_recommended"])
    def test_iteration_status_stops_on_repeated_remaining(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        entry = "- Cycle: {number}/5\n- Decision: continue\n- Changed: attempt {number}\n- Verified: test\n- Remaining: same blocker\n"
        path.write_text("## 10:00 One\n" + entry.format(number=1) + "\n## 10:10 Two\n" + entry.format(number=2), encoding="utf-8")
        report = build_iteration_status(self.root, request="up to 5 cycles", task="repeat")
        self.assertTrue(report["repeated_remaining"])
        self.assertIn("same_remaining_repeated_twice", report["stop_reasons"])
        self.assertFalse(report["continue_recommended"])

    def test_iteration_status_uses_recorded_budget_mode_for_plain_status_request(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/3\n- Budget Mode: upper_bound\n- Decision: continue\n"
            "- Changed: attempt\n- Verified: test\n- Remaining: next\n",
            encoding="utf-8",
        )

        report = build_iteration_status(self.root, request="status checkpoint", task="repeat")

        self.assertEqual(3, report["budget"])
        self.assertEqual("upper_bound", report["budget_mode"])
