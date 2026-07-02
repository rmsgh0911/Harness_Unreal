"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class MemoryTests(HarnessBaseTestCase):
    def test_knowledge_does_not_match_tokens_inside_unrelated_words(self) -> None:
        docs = self.root / "Harness/docs"
        docs.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "Budget.md").write_text("# Capital Budget\n\nFinance only.\n", encoding="utf-8")
        report = build_knowledge(self.root, query="api")
        self.assertFalse(any(item["path"].endswith("Budget.md") for item in report["matches"]))
    def test_knowledge_routes_retained_docs_and_task_records(self) -> None:
        docs = self.root / "Harness/docs"
        tasks = self.root / "Harness/work/tasks"
        docs.mkdir(exist_ok=True)
        tasks.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "LockOn.md").write_text("# Lock-on Recovery\n\nLegacy lock-on retry evidence.\n", encoding="utf-8")
        (tasks / "lock-on.md").write_text("# Task: lock-on\n\n- Remaining: verify legacy retry\n", encoding="utf-8")
        report = build_knowledge(self.root, query="legacy lock-on retry")
        kinds = {item["kind"] for item in report["matches"]}
        self.assertIn("doc", kinds)
        self.assertIn("task", kinds)
        context = build_context(self.root, request="legacy lock-on retry")
        self.assertTrue(any(item["path"].endswith("LockOn.md") for item in context["existing_knowledge"]["matches"]))
    def test_korean_particles_do_not_hide_relevant_knowledge(self) -> None:
        docs = self.root / "Harness/docs"
        docs.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "Dashboard.md").write_text("# 대시보드 UI 경로\n\n위젯 수정 안내.\n", encoding="utf-8")
        report = build_knowledge(self.root, query="대시보드를 수정해줘")
        self.assertTrue(any(item["path"].endswith("Dashboard.md") for item in report["matches"]))
        context = build_context(self.root, request="대시보드를 수정해줘")
        self.assertTrue(any(item["path"].endswith("Dashboard.md") for item in context["existing_knowledge"]["matches"]))
    def test_memory_add_rebuild_and_query_uses_daily_jsonl(self) -> None:
        args = argparse.Namespace(
            id="00000000-0000-4000-8000-000000000123",
            created_at="2026-07-01T12:00:00+09:00",
            status="confirmed",
            title="UMG PIE visibility",
            body="AddToViewport in BeginPlay is visible only in PIE.",
            tags="unreal,umg,pie",
            source="Harness/docs/AgentFieldGuide.md",
        )
        added = add_memory_entry(self.root, args)
        self.assertEqual("Harness/data/memory/2026-07-01.jsonl", added["shard"])
        self.assertTrue((self.root / "Harness/data/memory/2026-07-01.jsonl").exists())
        rebuilt = rebuild_memory_cache(self.root)
        self.assertTrue(rebuilt["ok"])
        validation = validate_memory(self.root)
        self.assertTrue(validation["ok"])
        self.assertEqual(1, validation["entries"])
        query_args = argparse.Namespace(query="widget visible PIE", include_draft=False, limit=5, max_chars=1600)
        result = query_memory_entries(self.root, query_args)
        self.assertEqual(1, result["count"])
        self.assertEqual("UMG PIE visibility", result["results"][0]["title"])
    def test_memory_promote_demote_updates_jsonl_and_cache(self) -> None:
        entry_id = "00000000-0000-4000-8000-000000000127"
        args = argparse.Namespace(
            id=entry_id,
            created_at="2026-07-05T12:00:00+09:00",
            status="draft",
            title="Reviewable memory",
            body="Draft memory can be promoted after review.",
            tags="memory",
            source="",
        )
        add_memory_entry(self.root, args)
        promoted = update_memory_status(self.root, entry_id, "confirmed")
        self.assertTrue(promoted["ok"])
        query_args = argparse.Namespace(query="reviewable", include_draft=False, limit=5, max_chars=1600)
        self.assertEqual(1, query_memory_entries(self.root, query_args)["count"])
        demoted = update_memory_status(self.root, entry_id, "draft")
        self.assertTrue(demoted["ok"])
        self.assertEqual(0, query_memory_entries(self.root, query_args)["count"])
    def test_memory_prune_fails_when_jsonl_has_errors(self) -> None:
        memory = self.root / "Harness/data/memory"
        memory.mkdir(parents=True, exist_ok=True)
        (memory / "2026-07-07.jsonl").write_text("{not json}\n", encoding="utf-8")
        prune_args = argparse.Namespace(write=False, prune_draft_days=30, prune_max_body_chars=600)
        report = prune_memory(self.root, prune_args)
        self.assertFalse(report["ok"])
        self.assertTrue(report["doctor"]["errors"])
    def test_memory_query_excludes_draft_by_default(self) -> None:
        args = argparse.Namespace(
            id="00000000-0000-4000-8000-000000000124",
            created_at="2026-07-02T12:00:00+09:00",
            status="draft",
            title="Draft encoding note",
            body="Verify this before relying on it.",
            tags="encoding",
            source="",
        )
        add_memory_entry(self.root, args)
        query_args = argparse.Namespace(query="encoding", include_draft=False, limit=5, max_chars=1600)
        self.assertEqual(0, query_memory_entries(self.root, query_args)["count"])
        query_args.include_draft = True
        self.assertEqual(1, query_memory_entries(self.root, query_args)["count"])
    def test_memory_validation_rejects_duplicate_ids(self) -> None:
        memory = self.root / "Harness/data/memory"
        memory.mkdir(parents=True, exist_ok=True)
        duplicate = (
            '{"id":"00000000-0000-4000-8000-000000000125","created_at":"2026-07-03T12:00:00+09:00",'
            '"status":"confirmed","title":"One","body":"First body.","tags":["test"],"source":""}\n'
        )
        (memory / "2026-07-03.jsonl").write_text(duplicate + duplicate, encoding="utf-8")
        validation = validate_memory(self.root)
        self.assertFalse(validation["ok"])
        self.assertTrue(any("duplicate memory id" in item["error"] for item in validation["errors"]))
