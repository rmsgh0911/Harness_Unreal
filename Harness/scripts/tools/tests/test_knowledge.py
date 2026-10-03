"""Regression tests for bounded, priority-aware Harness knowledge search."""

from _harness_test_base import *  # noqa: F401,F403


class KnowledgeTests(HarnessBaseTestCase):
    def test_current_correction_outranks_invalidated_more_relevant_match(self):
        folder = self.root / "Harness/work/cycles"
        folder.mkdir(exist_ok=True)
        (folder / "fix.md").write_text("## Old\n- Invalidated: true\nneedle uniquealpha uniquebeta\n\n## New\n- Supersedes: #Old\nneedle\n", encoding="utf-8")
        report = build_knowledge(self.root, query="needle uniquealpha uniquebeta", limit=1)
        self.assertEqual("New", report["matches"][0]["section"])

    def test_local_supersedes_does_not_invalidate_another_files_same_heading(self):
        folder = self.root / "Harness/work/cycles"
        folder.mkdir(exist_ok=True)
        (folder / "one.md").write_text("## Old\nneedle\n\n## New\n- Supersedes: Old\nneedle\n", encoding="utf-8")
        (folder / "two.md").write_text("## Old\nneedle\n", encoding="utf-8")
        report = build_knowledge(self.root, query="needle")
        self.assertEqual("current", next(item for item in report["matches"] if item["path"].endswith("two.md"))["status"])

    def test_invalidated_result_surfaces_replacement(self) -> None:
        cycles = self.root / "Harness/work/cycles"
        cycles.mkdir(exist_ok=True)
        path = cycles / "placement.md"
        path.write_text(
            "## Old Placement\n- Invalidated: true\n- Changed: axis placement\n\n"
            "## Corrected Placement\n- Supersedes: Harness/work/cycles/placement.md#Old Placement\n"
            "- Changed: corrected axis placement\n",
            encoding="utf-8",
        )

        report = build_knowledge(self.root, query="axis placement")
        results = {item["section"]: item for item in report["matches"]}

        self.assertEqual("invalidated", results["Old Placement"]["status"])
        self.assertEqual(
            "Harness/work/cycles/placement.md#Corrected Placement",
            results["Old Placement"]["replacement"],
        )
        self.assertEqual("current", results["Corrected Placement"]["status"])

    def test_current_task_stays_discoverable_after_more_than_two_hundred_docs(self) -> None:
        docs = self.root / "Harness/docs"
        tasks = self.root / "Harness/work/tasks"
        docs.mkdir(exist_ok=True)
        tasks.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        for index in range(205):
            (docs / f"history-{index:03}.md").write_text(f"# Historical {index}\n\nold material\n", encoding="utf-8")
        current = tasks / "zz-current.md"
        current.write_text("# Current task\n\nneedle-current-contract\n", encoding="utf-8")

        report = build_knowledge(self.root, query="needle-current-contract", max_files=20, preferred_paths=[current])

        self.assertTrue(any(item["path"].endswith("zz-current.md") for item in report["matches"]))
        self.assertGreater(report["omitted_files"], 0)
        self.assertGreater(report["omitted_counts"].get("doc", 0), 0)
        self.assertIn("--max-files", report["broader_query"])

    def test_explicit_path_precedes_a_large_task_collection(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        tasks.mkdir(exist_ok=True)
        for index in range(205):
            (tasks / f"task-{index:03}.md").write_text("# Old task\n\nunrelated\n", encoding="utf-8")
        current = tasks / "zz-explicit.md"
        current.write_text("# Explicit task\n\npriority-marker\n", encoding="utf-8")

        report = build_knowledge(self.root, query="priority-marker", max_files=10, preferred_paths=[current])

        self.assertEqual("Harness/work/tasks/zz-explicit.md", report["matches"][0]["path"])
        self.assertGreater(report["omitted_counts"].get("task", 0), 0)
