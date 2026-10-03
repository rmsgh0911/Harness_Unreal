"""Adversarial contracts: unknown or malformed evidence must not become authority."""
from _harness_test_base import *  # noqa: F401,F403
import test_subagent as fixtures
import harness_subagent as agent


class SubagentPrecisionTests(HarnessBaseTestCase):
    _git = fixtures.SubagentTests._git
    _init_git = fixtures.SubagentTests._init_git

    def registry(self):
        fixtures.write_registry(self.root)
        return self.root / "Harness/config/agents.json"

    def test_registry_malformed_role_fields_fail_without_exception(self):
        path = self.registry()
        original = json.loads(path.read_text(encoding="utf-8"))
        for key, value in (("evidence_profile", []), ("evidence_profile", {}),
                           ("display_name", []), ("purpose", ""), ("display_name", "x" * 257)):
            with self.subTest(key=key, value=value):
                data = json.loads(json.dumps(original))
                data["subagent_roles"]["current-status"][key] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertFalse(agent.validate_registry(self.root)["ok"])
                self.assertFalse(agent.build_packet(self.root, "current-status")["ok"])

    def test_empty_contract_cannot_produce_a_delegation_prompt(self):
        self.registry()
        contract = self.root / "Harness/agents/current-status.md"
        for value in ("", " \n\t"):
            contract.write_text(value, encoding="utf-8")
            result = agent.build_packet(self.root, "current-status")
            self.assertFalse(result["ok"])
            self.assertEqual("", result["prompt"])

    def test_prompt_uses_only_validated_bounded_contract_snapshot(self):
        self.registry()
        contract = self.root / "Harness/agents/current-status.md"
        before = contract.read_bytes()
        def replace_after_validation(*args):
            contract.write_text("REPLACED-AFTER-VALIDATION" * 4000, encoding="utf-8")
            return {"readiness": "ready"}, []
        with patch.object(agent, "_current_status_evidence", side_effect=replace_after_validation):
            report = agent.build_packet(self.root, "current-status")
        import hashlib
        self.assertTrue(report["ok"])
        self.assertNotIn("REPLACED-AFTER-VALIDATION", report["prompt"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), report["evidence"]["instruction_snapshot"]["sha256"])

    def test_role_contract_cannot_be_a_link_to_another_project_document(self):
        self.registry()
        contract = self.root / "Harness/agents/current-status.md"
        contract.unlink()
        try:
            contract.symlink_to(self.root / "HARNESS.md")
        except OSError:
            self.skipTest("symlink permission unavailable")
        self.assertFalse(agent.validate_registry(self.root)["ok"])

    def test_git_read_timeout_covers_a_silent_process(self):
        import time
        started = time.monotonic()
        with patch.object(agent, "_git_command", return_value=[sys.executable, "-c", "import time; time.sleep(5)"]), patch.object(agent, "GIT_COMMAND_TIMEOUT", 0.2):
            report = agent._run_git_prefix(self.root, [], max_bytes=100)
        self.assertFalse(report["ok"])
        self.assertIn("timed out", report["stderr"])
        self.assertLess(time.monotonic() - started, 3)

    def test_git_drains_large_stderr_without_deadlock_or_unbounded_report(self):
        command = [sys.executable, "-c", "import sys; sys.stderr.write('x'*200000); sys.stderr.flush(); sys.stdout.write('ok')"]
        with patch.object(agent, "_git_command", return_value=command):
            report = agent._run_git_prefix(self.root, [], max_bytes=100)
        self.assertTrue(report["ok"])
        self.assertEqual("ok", report["stdout"])
        self.assertLessEqual(len(report["stderr"]), 4096)

    def test_snapshot_uses_full_object_ids_independent_of_git_abbreviation(self):
        self.registry()
        self._init_git()
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        self._git("add", "tracked.txt")
        self._git("config", "core.abbrev", "4")
        first = agent.collect_git_evidence(self.root)
        self._git("config", "core.abbrev", "40")
        second = agent.collect_git_evidence(self.root)
        self.assertEqual(first["staged"]["snapshot_sha256"], second["staged"]["snapshot_sha256"])
        self.assertEqual(str(self.root.resolve()), first["snapshot_components"]["root"])
        self.assertIn("not read or hashed", first["consistency_scope"]["untracked_file_contents"])

    def test_invalid_or_oversized_records_are_not_partial_success_text(self):
        self.registry()
        state = self.root / "Harness/work/state.md"
        for raw in (b"\xff", b"x" * (agent.MAX_RECORD_SOURCE_BYTES + 1)):
            state.write_bytes(raw)
            with patch.object(agent, "build_context") as context:
                report = agent.build_packet(self.root, "current-status")
            context.assert_not_called()
            self.assertFalse(report["ready"])
            self.assertEqual("", report["evidence"]["records"]["state"]["text"])

    def test_record_evidence_refuses_links_before_context_reads_them(self):
        self.registry()
        state = self.root / "Harness/work/state.md"
        state.unlink()
        outside = self.root / "private-note.txt"
        outside.write_text("OUTSIDE-RECORD-MUST-NOT-LEAK", encoding="utf-8")
        try:
            state.symlink_to(outside)
        except OSError:
            self.skipTest("symlink permission unavailable")
        with patch.object(agent, "build_context") as context:
            report = agent.build_packet(self.root, "current-status")
        context.assert_not_called()
        self.assertNotIn("OUTSIDE-RECORD-MUST-NOT-LEAK", report["prompt"])
        self.assertFalse(report["ready"])

    def test_invalid_utf8_git_path_is_not_an_authoritative_listing(self):
        command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([255,0]))"]
        with patch.object(agent, "_git_command", return_value=command):
            report = agent._run_git_tokens(self.root, [])
        self.assertFalse(report["ok"])
        self.assertTrue(report["token_truncated"])

    def test_status_callback_has_byte_bounds_and_preserves_literal_arrow(self):
        def stream(root, args, **kwargs):
            callback = kwargs["on_token"]
            callback("?? Binaries/f -> harmless.txt", False)
            for index in range(79):
                callback("?? " + str(index) + "x" * 6000, False)
            return {"ok": True, "exit_code": 0, "stderr": ""}
        with patch.object(agent, "_run_git_tokens", side_effect=stream):
            report = agent._collect_status(self.root)
        self.assertGreater(report["omitted"], 0)
        self.assertLessEqual(sum(len(item.encode()) for item in report["sample"]), agent.MAX_PATH_SAMPLE_BYTES)
        self.assertEqual("generated_directory", report["risk_sample"][0]["reason"])

    def test_git_failure_diagnostic_does_not_echo_sensitive_values(self):
        failure = {"ok": False, "stderr": "api_key = DIAGNOSTIC-MUST-NOT-LEAK", "stdout": ""}
        with patch.object(agent, "_run_git_prefix", return_value=failure):
            report = agent.collect_git_evidence(self.root)
        self.assertFalse(report["available"])
        self.assertNotIn("DIAGNOSTIC-MUST-NOT-LEAK", json.dumps(report))

    def test_commit_paths_alone_cannot_authorize_a_semantic_draft(self):
        self.registry()
        self._init_git()
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8", newline="\n")
        self._git("add", "tracked.txt")
        metadata = agent.build_packet(self.root, "commit-explainer")
        self.assertTrue(metadata["evidence"]["scope_ready"], metadata["warnings"])
        self.assertFalse(metadata["ready"])
        complete = agent.build_packet(self.root, "commit-explainer", include_staged_patch=True)
        self.assertTrue(complete["ready"], complete["warnings"])

    def test_prompt_preserves_warnings_and_caller_provenance(self):
        self.registry()
        report = agent.build_packet(self.root, "commit-explainer", verification=["all tests passed"])
        packet = json.loads(report["prompt"].split("## Delegation Packet\n\n", 1)[1])
        self.assertEqual(report["warnings"], packet["evidence"]["warnings"])
        self.assertTrue(packet["evidence"]["blockers"])
        self.assertFalse(packet["evidence"]["verification_provenance"]["executed_by_collector"])
        self.assertFalse(packet["evidence"]["verification_provenance"]["snapshot_bound"])

    def test_missing_records_and_context_warnings_cannot_mean_complete_status(self):
        self.registry()
        self._init_git()
        (self.root / "Harness/work/state.md").unlink()
        report = agent.build_packet(self.root, "current-status")
        self.assertFalse(report["ready"])
        self.assertTrue(any("missing: state" in item for item in report["warnings"]))
        with patch.object(agent, "collect_git_evidence", return_value={"available": False, "error": "missing git"}):
            report = agent.build_packet(self.root, "current-status")
        self.assertIsNone(report["evidence"]["diff_guard"]["changed_count"])
        self.assertIsNone(report["evidence"]["diff_guard"]["risk_count"])

    def test_commit_context_omission_survives_prompt_serialization(self):
        self.registry()
        (self.root / "Harness/work/state.md").write_bytes(b"\xff")
        report = agent.build_packet(self.root, "commit-explainer")
        self.assertTrue(any("context collection omitted" in item for item in report["warnings"]))
        self.assertIn("context collection omitted", report["prompt"])

    def test_latest_verification_ignores_a_fenced_example_heading(self):
        path = self.root / "Harness/work/state.md"
        path.write_text("# State\n```markdown\n## Latest Verification\n- invented pass\n```\n## Latest Verification\n- actual unknown\n", encoding="utf-8")
        result = agent._read_bounded_markdown_section(path, "## Latest Verification")
        self.assertNotIn("invented pass", result["text"])
        self.assertIn("actual unknown", result["text"])

    def test_helper_packet_does_not_search_unrelated_history_or_memory(self):
        self.registry()
        with patch("harness_knowledge.build_history") as history, patch("harness_knowledge.build_knowledge") as knowledge:
            report = agent.build_packet(self.root, "current-status", request="summarize prior needle work")
        self.assertTrue(report["ok"])
        history.assert_not_called()
        knowledge.assert_not_called()
