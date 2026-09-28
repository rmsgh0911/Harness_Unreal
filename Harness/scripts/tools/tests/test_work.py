"""Tests for transactional task closeout."""

from _harness_test_base import *  # noqa: F401,F403

from harness_work import apply_close, build_close_plan


class WorkCloseTests(HarnessBaseTestCase):
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
