"""Derived execution-history discovery without truncation or implicit writes."""
from _harness_test_base import *  # noqa: F401,F403
import harness_knowledge as knowledge


class HistoryTests(HarnessBaseTestCase):
    def test_failed_correction_cannot_supersede_current_evidence_in_either_source(self):
        path = self.record(folder="cycles")
        path.write_text("## Good\n- Verified: needle\n- Acceptance: passed\n"
                        "## Failed\n- Verified: needle\n- Acceptance: failed\n- Supersedes: #Good\n", encoding="utf-8")
        for cached in (False, True):
            if cached:
                knowledge.rebuild_history(self.root)
            rows = knowledge.build_history(self.root, "needle")["results"]
            self.assertEqual(["current", "evidence_gap"], [item["status"] for item in rows])
            self.assertEqual("Good", rows[0]["section"])

    def test_history_does_not_use_fenced_invalidation_as_real_metadata(self):
        path = self.record()
        path.write_text(path.read_text(encoding="utf-8") + "\n```text\n- Invalidated: true\n```\n", encoding="utf-8")
        row = knowledge.build_history(self.root, "needle")["results"][0]
        self.assertEqual("current", row["status"])
        self.assertEqual("accepted", row["evidence_status"])

    def test_sentence_punctuation_and_identifier_parts_match_in_both_sources(self):
        self.record(body="Fixed viewport. Inspect Source/UI/Dashboard.cpp and lock-on.")
        for cached in (False, True):
            if cached:
                knowledge.rebuild_history(self.root)
            for query in ("viewport", "Dashboard", "lock"):
                with self.subTest(cached=cached, query=query):
                    self.assertEqual(1, knowledge.build_history(self.root, query)["count"])

    def test_nested_cycle_details_and_task_updated_date_remain_searchable(self):
        path = self.record(body="overview")
        path.write_text(path.read_text(encoding="utf-8") + "\n### Details\nneedle nested evidence\n", encoding="utf-8")
        self.assertEqual(1, knowledge.build_history(self.root, "needle")["count"])
        task = self.root / "Harness/work/tasks/date.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text("# Task: date\n- Updated: 2026-09-29T12:00:00+09:00\n\n## Scope\nneedle\n", encoding="utf-8")
        self.assertEqual(1, knowledge.build_history(self.root, "needle", task="date", since="2026-09-01")["count"])
        self.assertEqual(0, knowledge.build_history(self.root, "the")["count"])

    def test_cache_payload_shape_corruption_falls_back_without_write(self):
        import sqlite3
        self.record()
        knowledge.rebuild_history(self.root)
        cache = self.root / "Harness/data/history.sqlite"
        connection = sqlite3.connect(cache)
        connection.execute("UPDATE history_record SET payload = '{}' ")
        connection.commit()
        connection.close()
        original = cache.read_bytes()
        result = knowledge.build_history(self.root, "needle")
        self.assertTrue(result["ok"])
        self.assertEqual("unavailable", result["cache_status"])
        self.assertEqual(1, result["count"])
        self.assertEqual(original, cache.read_bytes())

    def test_archive_keeps_unambiguous_active_path_supersedes_reference(self):
        path = self.record(folder="cycles")
        path.write_text("## Old\nneedle\n\n## New\n- Supersedes: Harness/work/cycles/recovery.md#Old\nneedle\n", encoding="utf-8")
        before = knowledge.build_history(self.root, "needle")
        archived = self.root / "Harness/work/archive/2026-09/cycles/recovery.md"
        archived.parent.mkdir(parents=True)
        path.rename(archived)
        after = knowledge.build_history(self.root, "needle")
        self.assertEqual([item["status"] for item in before["results"]], [item["status"] for item in after["results"]])
        self.assertEqual("superseded", after["results"][-1]["status"])

    def test_context_exposes_history_and_memory_errors_with_provenance(self):
        from harness_context import format_text
        path = self.record()
        folder = self.root / "Harness/data/memory"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "broken.jsonl").write_text("{bad}", encoding="utf-8")
        context = build_context(self.root, request="needle")
        text = format_text(context)
        self.assertIn("memory has source errors", text)
        self.assertEqual(1, context["existing_knowledge"]["history"]["count"])
        self.assertIn(path.relative_to(self.root).as_posix(), text)

    def record(self, task="recovery", folder="archive/2026-08/cycles", body="needle retry verified"):
        path = self.root / "Harness/work" / folder / (task + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Cycles\n\n## Cycle 1\n- Recorded: 2026-08-10T09:00:00+09:00\n"
                        "- Decision: stop_success\n- Verified:\n  - " + body + "\n"
                        "- Evidence Kind: runtime\n- Evidence Exit Code: 0\n- Acceptance: passed\n"
                        "- Input Revision: abc123\n", encoding="utf-8")
        return path

    def test_archive_discovery_is_independent_of_document_bound(self):
        docs = self.root / "Harness/docs"
        docs.mkdir(exist_ok=True)
        for number in range(205):
            (docs / f"filler{number}.md").write_text("# Noise\n", encoding="utf-8")
        self.record()
        report = knowledge.build_history(self.root, "needle")
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["count"])
        self.assertEqual("accepted", report["results"][0]["evidence_status"])
        self.assertEqual("abc123", report["results"][0]["input_revision"])
        self.assertTrue(report["results"][0]["archived"])
        self.assertFalse((self.root / "Harness/data/history.sqlite").exists())

    def test_cache_and_markdown_have_equivalent_filters(self):
        self.record()
        self.record(task="another", body="대시보드 recovery")
        before = knowledge.build_history(self.root, "대시보드를", task="another", decision="stop_success", since="2026-08-01")
        self.assertTrue(knowledge.rebuild_history(self.root)["ok"])
        after = knowledge.build_history(self.root, "대시보드를", task="another", decision="stop_success", since="2026-08-01")
        self.assertEqual(before["results"], after["results"])
        self.assertEqual("sqlite", after["source"])
        self.assertEqual(0, knowledge.build_history(self.root, "needle", since="2026-09-01")["count"])

    def test_cache_detects_source_edit_delete_and_corruption_without_writing(self):
        path = self.record()
        knowledge.rebuild_history(self.root)
        cache = self.root / "Harness/data/history.sqlite"
        original = cache.read_bytes()
        path.write_text(path.read_text(encoding="utf-8").replace("needle", "updated"), encoding="utf-8")
        self.assertEqual(1, knowledge.build_history(self.root, "updated")["count"])
        self.assertEqual(original, cache.read_bytes())
        path.unlink()
        self.assertEqual(0, knowledge.build_history(self.root, "needle")["count"])
        cache.write_bytes(b"corrupt")
        self.assertEqual("unavailable", knowledge.build_history(self.root, "needle")["cache_status"])
        self.assertEqual(b"corrupt", cache.read_bytes())
        self.assertTrue(knowledge.rebuild_history(self.root)["ok"])

    def test_history_reads_past_old_fifty_thousand_character_bound(self):
        self.record(body="noise " * 10000 + "needle")
        report = knowledge.build_history(self.root, "needle", max_chars=1200)
        self.assertEqual(1, report["count"])
        self.assertTrue(report["results"][0]["truncated"])
        self.assertLessEqual(report["result_chars"], 1200)

    def test_history_invalid_utf8_reports_error_and_keeps_cache(self):
        path = self.record()
        knowledge.rebuild_history(self.root)
        cache = self.root / "Harness/data/history.sqlite"
        original = cache.read_bytes()
        path.write_bytes(b"\xff")
        self.assertFalse(knowledge.build_history(self.root, "needle")["ok"])
        with self.assertRaises(UnicodeError):
            knowledge.rebuild_history(self.root)
        self.assertEqual(original, cache.read_bytes())

    def test_invalidated_record_is_not_mistaken_for_accepted_current_truth(self):
        path = self.record()
        with path.open("a", encoding="utf-8") as stream:
            stream.write("- Invalidated: true\n")
        result = knowledge.build_history(self.root, "needle")["results"][0]
        self.assertEqual("invalidated", result["status"])
        self.assertEqual("invalidated", result["evidence_status"])
