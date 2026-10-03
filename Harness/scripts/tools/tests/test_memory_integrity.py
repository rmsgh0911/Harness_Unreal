"""Memory cache freshness, failure safety, and retrieval regressions."""
import os
import uuid

from _harness_test_base import *  # noqa: F401,F403
import harness_memory as memory


class MemoryIntegrityTests(HarnessBaseTestCase):
    def test_prune_preserves_confirmed_copy_when_old_draft_is_stale(self):
        self.add(created_at="2020-01-01T12:00:00+09:00", status="draft")
        confirmed = self.add()
        report = memory.prune_memory(self.root, argparse.Namespace(write=True, prune_draft_days=30, prune_max_body_chars=600))
        self.assertTrue(report["ok"])
        self.assertNotIn(confirmed["entry"]["id"], report["removed"])
        self.assertEqual([confirmed["entry"]["id"]], [row["id"] for row in self.query()["results"]])

    def test_cache_read_race_cannot_return_demoted_confirmed_entry(self):
        added = self.add()
        path = self.root / added["shard"]
        original_read = memory.rows_from_cache
        def race(*args, **kwargs):
            rows = original_read(*args, **kwargs)
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["status"] = "draft"
            path.write_text(json.dumps(raw), encoding="utf-8")
            return rows
        with patch("harness_memory.rows_from_cache", side_effect=race):
            report = self.query()
        self.assertEqual([], report["results"])
        self.assertEqual("jsonl", report["source"])

    def test_invalid_utf8_is_structured_source_error(self):
        added = self.add()
        (self.root / added["shard"]).write_bytes(b"\xff")
        report = self.query()
        self.assertFalse(report["ok"])
        self.assertIn("UTF-8", report["errors"][0]["error"])
        self.assertFalse(memory.validate_memory(self.root)["ok"])

    def test_query_during_writer_lock_is_not_accepted_partial_snapshot(self):
        self.add()
        with memory.write_lock(self.root):
            report = self.query()
        self.assertFalse(report["ok"])
        self.assertEqual([], report["results"])

    def test_rebuild_repairs_incompatible_derived_schema(self):
        import sqlite3
        self.add()
        with sqlite3.connect(memory.db_path(self.root)) as connection:
            connection.execute("DROP TABLE memory_entry")
            connection.execute("CREATE TABLE memory_entry (wrong TEXT)")
        connection.close()
        self.assertTrue(memory.rebuild_cache(self.root)["ok"])
        self.assertEqual(1, self.query()["count"])

    def test_sql_prefilter_avoids_loading_unrelated_memory_rows(self):
        added = self.add()
        path = self.root / added["shard"]
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = [raw, *(dict(raw, id=str(uuid.uuid4()), title=f"irrelevant {number}", body="noise") for number in range(300))]
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        fallback = self.query()
        memory.rebuild_cache(self.root)
        cached = self.query()
        self.assertEqual(fallback["results"], cached["results"])
        self.assertEqual(1, cached["candidate_count"])
        self.assertEqual(301, fallback["candidate_count"])

    def test_outside_shard_link_fails_closed(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.jsonl"
            target.write_text("{}", encoding="utf-8")
            memory.ensure_layout(self.root)
            link = memory.memory_dir(self.root) / "outside.jsonl"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation unavailable")
            self.assertFalse(memory.validate_memory(self.root)["ok"])
            with self.assertRaises(ValueError):
                self.add()
            self.assertEqual("{}", target.read_text(encoding="utf-8"))

    def add(self, **changes):
        values = dict(id=str(uuid.uuid4()), created_at="2026-09-01T12:00:00+09:00", status="confirmed",
                      title="needle", body="original", tags="", source="")
        values.update(changes)
        return memory.add_entry(self.root, argparse.Namespace(**values))

    def query(self, **changes):
        values = dict(query="needle", include_draft=False, limit=5, max_chars=1600)
        values.update(changes)
        return memory.query_memory(self.root, argparse.Namespace(**values))

    def test_modified_demoted_and_deleted_sources_invalidate_cache(self):
        added = self.add()
        shard = self.root / added["shard"]
        original_time = shard.stat().st_mtime_ns
        raw = json.loads(shard.read_text(encoding="utf-8"))
        raw["body"] = "modified"
        shard.write_text(json.dumps(raw), encoding="utf-8")
        os.utime(shard, ns=(original_time, original_time))
        result = self.query()
        self.assertEqual("jsonl", result["source"])
        self.assertEqual("modified", result["results"][0]["body"])
        raw["status"] = "draft"
        shard.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(0, self.query()["count"])
        shard.unlink()
        self.assertEqual(0, self.query()["count"])
        self.assertTrue(memory.memory_doctor(self.root)["cache"]["stale"])

    def test_corrupt_cache_falls_back_without_writing(self):
        self.add()
        cache = memory.db_path(self.root)
        cache.write_bytes(b"not sqlite")
        result = self.query()
        self.assertTrue(result["ok"])
        self.assertEqual("jsonl", result["source"])
        self.assertEqual("unavailable", result["cache"]["status"])
        self.assertTrue(result["warnings"])
        self.assertEqual(b"not sqlite", cache.read_bytes())

    def test_cacheless_query_remains_read_only(self):
        result = self.query()
        self.assertEqual(0, result["count"])
        self.assertFalse(memory.db_path(self.root).exists())

    def test_new_shard_and_invalid_shard_cannot_hide_behind_cache(self):
        self.add()
        shard = memory.memory_dir(self.root) / "2026-09-02.jsonl"
        shard.write_text("{invalid", encoding="utf-8")
        result = self.query()
        self.assertFalse(result["ok"])
        self.assertEqual("jsonl", result["source"])

    def test_add_after_external_change_does_not_bless_old_rows(self):
        added = self.add()
        shard = self.root / added["shard"]
        raw = json.loads(shard.read_text(encoding="utf-8"))
        raw["body"] = "external update"
        shard.write_text(json.dumps(raw) + "\n", encoding="utf-8")
        self.add(title="another")
        self.assertEqual("external update", self.query()["results"][0]["body"])

    def test_duplicate_id_is_rejected_before_mutation_including_case_alias(self):
        entry_id = "aaaaaaaa-0000-4000-8000-000000000001"
        added = self.add(id=entry_id)
        shard = self.root / added["shard"]
        original = shard.read_bytes()
        with self.assertRaisesRegex(ValueError, "duplicate memory id"):
            self.add(id=entry_id.upper())
        self.assertEqual(original, shard.read_bytes())
        self.assertTrue(memory.validate_memory(self.root)["ok"])

    def test_naive_timestamp_is_rejected_and_existing_bad_record_is_reported(self):
        with self.assertRaises(ValueError):
            self.add(created_at="2026-08-01T12:00:00", status="draft")
        added = self.add()
        shard = self.root / added["shard"]
        raw = json.loads(shard.read_text(encoding="utf-8"))
        raw.update(created_at="2026-08-01T12:00:00", status="draft")
        shard.write_text(json.dumps(raw), encoding="utf-8")
        self.assertFalse(memory.memory_doctor(self.root)["ok"])
        self.assertFalse(memory.update_status(self.root, raw["id"], "confirmed")["ok"])

    def test_cache_promotion_failure_rolls_back_source_change(self):
        added = self.add()
        shard = self.root / added["shard"]
        original = shard.read_bytes()
        replace = memory.os.replace
        def fail_cache(source, destination):
            if Path(destination) == memory.db_path(self.root):
                raise OSError("simulated cache promotion failure")
            return replace(source, destination)
        with patch("harness_memory.os.replace", side_effect=fail_cache):
            with self.assertRaises(OSError):
                memory.update_status(self.root, added["entry"]["id"], "draft")
        self.assertEqual(original, shard.read_bytes())
        self.assertEqual("confirmed", self.query()["results"][0]["status"])
        self.assertFalse((memory.data_dir(self.root) / ".memory.lock").exists())

    def test_rebuild_repairs_corrupt_cache_and_queries_stay_read_only(self):
        self.add()
        memory.db_path(self.root).write_bytes(b"broken")
        self.assertTrue(memory.rebuild_cache(self.root)["ok"])
        self.assertEqual("sqlite", self.query()["source"])

    def test_add_rejects_concurrent_writer(self):
        with memory.write_lock(self.root):
            with self.assertRaisesRegex(ValueError, "writer lock"):
                self.add()
        self.assertEqual(0, memory.validate_memory(self.root)["entries"])

    def test_add_after_shard_without_terminal_newline_preserves_valid_lines(self):
        added = self.add()
        shard = self.root / added["shard"]
        shard.write_bytes(shard.read_bytes().rstrip(b"\r\n"))
        self.add()
        self.assertEqual(2, memory.validate_memory(self.root)["entries"])

    def test_budget_includes_first_body_tags_and_all_result_metadata(self):
        self.add(body='긴 내용 "\\\n' * 1000)
        result = self.query(max_chars=500)
        self.assertEqual(1, result["count"])
        self.assertTrue(result["results"][0]["truncated"])
        self.assertLessEqual(memory.result_chars(result["results"]), 500)
        self.add(tags="huge" * 1000)
        result = self.query(max_chars=600)
        self.assertEqual(1, result["omitted_count"])
        self.assertLessEqual(result["result_chars"], 600)

    def test_small_budget_can_omit_without_truncating_provenance(self):
        self.add(source="important/path/" * 100)
        result = self.query(max_chars=200)
        self.assertEqual([], result["results"])
        self.assertEqual(1, result["omitted_count"])
        with self.assertRaises(ValueError):
            self.query(max_chars=0)
        with self.assertRaises(ValueError):
            self.query(limit=0)

    def test_search_uses_words_and_shared_korean_particle_normalization(self):
        self.add(title="Capital budget", body="Finance only")
        self.assertEqual(0, self.query(query="api")["count"])
        self.add(title="대시보드 UI 경로", body="위젯 수정 안내")
        self.assertEqual(1, self.query(query="대시보드를 수정해줘")["count"])

    def test_aggregate_budget_and_timezone_order(self):
        self.add(title="needle early", created_at="2026-09-01T12:00:00+09:00")
        self.add(title="needle late", created_at="2026-09-01T04:00:00+00:00")
        result = self.query(max_chars=600)
        self.assertEqual("needle late", result["results"][0]["title"])
        self.assertLessEqual(result["result_chars"], 600)
