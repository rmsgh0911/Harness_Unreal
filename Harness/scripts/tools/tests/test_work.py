"""Tests for transactional task closeout."""

from _harness_test_base import *  # noqa: F401,F403

from harness_work import apply_close, build_close_plan, render_completed_task


class WorkCloseTests(HarnessBaseTestCase):
    def test_close_changes_only_leading_metadata_and_preserves_crlf(self):
        source = "# Task\r\n- Status: active\r\n- Updated: yesterday\r\n## Example\r\n- Status: planned\r\n- Updated: example\r\n"
        result = render_completed_task(source)
        self.assertIn("- Status: completed\r\n", result)
        self.assertTrue(result.endswith("## Example\r\n- Status: planned\r\n- Updated: example\r\n"))

    def test_blank_or_example_status_cannot_close_or_archive(self):
        task, _ = self.make_records()
        for source in ("# Task\n- Status: \n- Owner: Codex\n", "# Task\n## Example\n- Status: completed\n",
                       "# Task\n```text\n- Status: completed\n```\n"):
            task.write_text(source, encoding="utf-8")
            self.assertFalse(build_close_plan(self.root, "close-me")["ready"])
            self.assertFalse(build_archive_plan(self.root, "close-me")["ready"])

    def test_close_refuses_linked_archive_without_modifying_sources(self):
        task, cycle = self.make_records()
        outside = self.root / "outside"
        outside.mkdir()
        archive = self.root / "Harness/work/archive"
        try:
            archive.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink permission unavailable")
        before = task.read_bytes(), cycle.read_bytes()
        self.assertFalse(build_close_plan(self.root, "close-me")["ready"])
        self.assertEqual(before, (task.read_bytes(), cycle.read_bytes()))
        self.assertEqual([], list(outside.iterdir()))

    def test_close_rejects_handwritten_early_exact_count_success(self):
        _, cycle = self.make_records()
        cycle.write_text(cycle.read_text(encoding="utf-8").replace("- Cycle: 1/1", "- Cycle: 1/8\n- Budget Mode: exact_count"), encoding="utf-8")
        self.assertFalse(build_close_plan(self.root, "close-me")["ready"])

    def test_close_rejects_invalidated_failed_and_unaccepted_evidence(self) -> None:
        task, cycle = self.make_records()
        original = cycle.read_text(encoding="utf-8")
        for suffix, expected in [("- Invalidated: true\n", "invalidated"), ("- Evidence Exit Code: 1\n", "verification_failed"), ("- Evidence Exit Code: unknown\n", "invalid_exit_code"), ("- Acceptance: \n", "invalid_metadata")]:
            with self.subTest(expected=expected):
                cycle.write_text(original + suffix, encoding="utf-8")
                report = build_close_plan(self.root, "close-me", "2026-09")
                self.assertFalse(report["ready"], report)
                self.assertEqual(expected, report["evidence_status"])
                self.assertTrue(task.exists())

    def make_records(self, decision: str = "stop_success", verified: str = "unit tests passed") -> tuple[Path, Path]:
        tasks = self.root / "Harness/work/tasks"
        cycles = self.root / "Harness/work/cycles"
        tasks.mkdir()
        cycles.mkdir()
        task = tasks / "close-me.md"
        cycle = cycles / "close-me.md"
        task.write_text(
            "# Task: close-me\n\n- Updated: 2026-01-01T00:00+09:00\n- Status: active\n",
            encoding="utf-8",
        )
        cycle.write_text(
            build_entry(
                "Final cycle",
                ["implemented"],
                [verified],
                ["none"],
                cycle_number=1,
                max_cycles=1,
                decision=decision,
                evidence_kinds=["runtime"],
                acceptance="passed",
            ),
            encoding="utf-8",
        )
        return task, cycle

    def test_close_preview_is_read_only(self) -> None:
        task, cycle = self.make_records()
        before = (task.read_bytes(), cycle.read_bytes())
        plan = build_close_plan(self.root, "close-me", "2026-09")
        self.assertTrue(plan["ready"])
        self.assertEqual(before, (task.read_bytes(), cycle.read_bytes()))

    def test_close_requires_success_decision_and_verification(self) -> None:
        self.make_records(decision="continue", verified="record needed")
        plan = build_close_plan(self.root, "close-me", "2026-09")
        self.assertFalse(plan["ready"])
        self.assertTrue(any("stop_success" in error for error in plan["errors"]))
        self.assertTrue(any("concrete verification" in error for error in plan["errors"]))

    def test_close_marks_completed_and_archives_pair(self) -> None:
        task, cycle = self.make_records()
        plan = build_close_plan(self.root, "close-me", "2026-09")
        moved = apply_close(self.root, plan)
        self.assertEqual(2, len(moved))
        self.assertFalse(task.exists())
        self.assertFalse(cycle.exists())
        archived = self.root / "Harness/work/archive/2026-09/tasks/close-me.md"
        self.assertIn("- Status: completed", archived.read_text(encoding="utf-8"))
        self.assertNotIn("2026-01-01T00:00", archived.read_text(encoding="utf-8"))

    def test_close_restores_task_when_archive_fails(self) -> None:
        task, cycle = self.make_records()
        original = task.read_bytes()
        plan = build_close_plan(self.root, "close-me", "2026-09")
        with patch("harness_work.apply_archive", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                apply_close(self.root, plan)
        self.assertEqual(original, task.read_bytes())
        self.assertTrue(cycle.exists())
