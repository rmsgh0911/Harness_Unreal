"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class ArchiveTests(HarnessBaseTestCase):
    def test_archive_before_moves_only_old_date_cycles_by_their_own_month(self) -> None:
        cycles = self.root / "Harness/work/cycles"
        cycles.mkdir()
        (cycles / "2026-05-08.md").write_text("# Cycle\n", encoding="utf-8")
        (cycles / "claude-2026-05-10.md").write_text("# Cycle\n", encoding="utf-8")
        (cycles / "2026-06-26-dashboard-panel-spacing.md").write_text("# Cycle\n", encoding="utf-8")
        (cycles / "model0619-dashboard.md").write_text("# Task cycle without date\n", encoding="utf-8")
        plan = build_archive_before_plan(self.root, "2026-06")
        self.assertTrue(plan["ready"])
        self.assertEqual(
            ["Harness/work/cycles/2026-05-08.md", "Harness/work/cycles/claude-2026-05-10.md"],
            [source["path"] for source in plan["sources"]],
        )
        moved = apply_archive(self.root, plan)
        self.assertEqual(2, len(moved))
        self.assertTrue((self.root / "Harness/work/archive/2026-05/cycles/2026-05-08.md").exists())
        self.assertTrue((self.root / "Harness/work/archive/2026-05/cycles/claude-2026-05-10.md").exists())
        self.assertTrue((cycles / "2026-06-26-dashboard-panel-spacing.md").exists())
        self.assertTrue((cycles / "model0619-dashboard.md").exists())
        index = (self.root / "Harness/work/archive/index.md").read_text(encoding="utf-8")
        self.assertIn("cycles 2026-05", index)
    def test_archive_before_reports_not_ready_without_old_cycles_or_valid_month(self) -> None:
        cycles = self.root / "Harness/work/cycles"
        cycles.mkdir()
        (cycles / "2026-06-17.md").write_text("# Cycle\n", encoding="utf-8")
        plan = build_archive_before_plan(self.root, "2026-06")
        self.assertFalse(plan["ready"])
        self.assertTrue(any("no date-based cycle records" in error for error in plan["errors"]))
        invalid = build_archive_before_plan(self.root, "../../outside")
        self.assertFalse(invalid["ready"])
    def test_archive_rejects_invalid_month_in_library_calls(self) -> None:
        with self.assertRaises(ValueError):
            validate_archive_month("../../outside")
        with self.assertRaises(ValueError):
            build_archive_plan(self.root, "safe-task", "../../outside")
    def test_archive_requires_completed_status_and_preserves_task_id(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        cycles = self.root / "Harness/work/cycles"
        tasks.mkdir()
        cycles.mkdir()
        (tasks / "done-task.md").write_text("# Task\n\n- Status: completed\n", encoding="utf-8")
        (cycles / "done-task.md").write_text("# Cycle\n", encoding="utf-8")
        plan = build_archive_plan(self.root, "done-task", "2026-06")
        self.assertTrue(plan["ready"])
        moved = apply_archive(self.root, plan)
        self.assertEqual(2, len(moved))
        index = (self.root / "Harness/work/archive/index.md").read_text(encoding="utf-8")
        self.assertIn("`done-task`", index)
    def test_archive_rolls_back_when_second_move_fails(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        cycles = self.root / "Harness/work/cycles"
        tasks.mkdir()
        cycles.mkdir()
        task = tasks / "rollback-task.md"
        cycle = cycles / "rollback-task.md"
        task.write_text("# Task\n\n- Status: completed\n", encoding="utf-8")
        cycle.write_text("# Cycle\n", encoding="utf-8")
        plan = build_archive_plan(self.root, "rollback-task", "2026-06")
        from harness_archive import shutil as archive_shutil
        real_move = archive_shutil.move

        def fail_cycle_move(source: Path, target: Path):
            if Path(source) == cycle:
                raise OSError("simulated second move failure")
            return real_move(source, target)

        with patch("harness_archive.shutil.move", side_effect=fail_cycle_move):
            with self.assertRaises(OSError):
                apply_archive(self.root, plan)
        self.assertTrue(task.exists())
        self.assertTrue(cycle.exists())
        self.assertFalse((self.root / "Harness/work/archive/2026-06/tasks/rollback-task.md").exists())
        self.assertFalse((self.root / "Harness/work/archive/index.md").exists())
        self.assertFalse((self.root / "Harness/work/archive").exists())
