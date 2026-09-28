"""Regression tests for bounded, read-only Harness subagent packets."""

import json
import io
import os
import shutil
import subprocess

from _harness_test_base import *  # noqa: F401,F403

import harness_subagent
from harness_subagent import build_packet, collect_git_evidence, validate_registry


def write_registry(root, *, current_path="Harness/agents/current-status.md", current_access="read_only") -> None:
    agents = root / "Harness/agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "current-status.md").write_text("# Current Status\n\nRead-only status contract.\n", encoding="utf-8")
    (agents / "commit-explainer.md").write_text("# Commit Explainer\n\nRead-only commit contract.\n", encoding="utf-8")
    data = {
        "version": 3,
        "delegation_policy": {
            "integration_owner": "primary_agent",
            "default_access": "read_only",
            "results_are_advisory": True,
            "primary_owns_durable_records": True,
            "pause_mutation_during_snapshot": True,
            "write_capable_parallel_work_requires_worktree": True,
            "common_forbidden_actions": [
                "edit_files",
                "write_durable_records",
                "stage",
                "unstage",
                "commit",
                "amend",
                "push",
                "tag",
                "change_branches",
            ],
        },
        "subagent_roles": {
            "current-status": {
                "display_name": "Current Status Curator",
                "purpose": "Summarize current evidence.",
                "instruction_file": current_path,
                "access": current_access,
                "evidence_profile": "current_status",
                "activation": ["status request"],
                "output_sections": [
                    "Snapshot",
                    "Overall",
                    "Confirmed Facts",
                    "Progress",
                    "Working Tree",
                    "Verification",
                    "Risks and Unknowns",
                    "Decisions Needed",
                    "Recommended Next",
                    "Evidence",
                ],
                "forbidden_actions": [
                    "edit_files",
                    "write_durable_records",
                    "stage",
                    "unstage",
                    "commit",
                    "amend",
                    "push",
                    "tag",
                    "change_branches",
                ],
            },
            "commit-explainer": {
                "display_name": "Commit Explanation Writer",
                "purpose": "Explain staged changes.",
                "instruction_file": "Harness/agents/commit-explainer.md",
                "access": "read_only",
                "evidence_profile": "staged_commit",
                "activation": ["commit request"],
                "output_sections": [
                    "Readiness",
                    "Staged Scope",
                    "Proposed Commit Message",
                    "Verification",
                    "Risks and Follow-up",
                    "Scope Boundary",
                    "Evidence",
                ],
                "forbidden_actions": [
                    "edit_files",
                    "write_durable_records",
                    "stage",
                    "unstage",
                    "commit",
                    "amend",
                    "push",
                    "tag",
                    "change_branches",
                ],
            },
        },
    }
    (root / "Harness/config/agents.json").write_text(json.dumps(data), encoding="utf-8")


class SubagentTests(HarnessBaseTestCase):
    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _init_git(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git is not available")
        self.assertEqual(0, self._git("init").returncode)
        self.assertEqual(0, self._git("config", "user.email", "harness@example.invalid").returncode)
        self.assertEqual(0, self._git("config", "user.name", "Harness Tests").returncode)
        self.assertEqual(0, self._git("config", "core.autocrlf", "false").returncode)
        tracked = self.root / "tracked.txt"
        tracked.write_text("base\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        self.assertEqual(0, self._git("commit", "-m", "Initial fixture").returncode)

    def test_git_collection_environment_disables_lazy_fetch_and_optional_locks(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": "C:/other/repository/.git",
                "GIT_INDEX_FILE": "C:/other/repository/alternate-index",
                "GIT_WORK_TREE": "C:/other/repository",
            },
        ):
            environment = harness_subagent._git_env()

        self.assertEqual("1", environment["GIT_NO_LAZY_FETCH"])
        self.assertEqual("1", environment["GIT_NO_REPLACE_OBJECTS"])
        self.assertEqual("0", environment["GIT_OPTIONAL_LOCKS"])
        self.assertEqual("0", environment["GIT_TERMINAL_PROMPT"])
        self.assertNotIn("GIT_DIR", environment)
        self.assertNotIn("GIT_INDEX_FILE", environment)
        self.assertNotIn("GIT_WORK_TREE", environment)

    def test_registry_accepts_two_read_only_roles(self) -> None:
        write_registry(self.root)

        report = validate_registry(self.root)

        self.assertTrue(report["ok"])
        self.assertEqual(["commit-explainer", "current-status"], [item["id"] for item in report["roles"]])

    def test_registry_rejects_escaping_prompt_and_write_access(self) -> None:
        write_registry(self.root, current_path="../outside.md", current_access="write")

        report = validate_registry(self.root)
        failures = [item["message"] for item in report["checks"] if not item["ok"]]

        self.assertFalse(report["ok"])
        self.assertTrue(any("instruction path is safe: current-status" in item for item in failures))
        self.assertTrue(any("role is read-only: current-status" in item for item in failures))

    def test_registry_rejects_absolute_backslash_and_missing_prompt_paths(self) -> None:
        for invalid_path in [
            "C:/outside.md",
            "Harness\\agents\\current-status.md",
            "Harness/agents/missing.md",
        ]:
            with self.subTest(invalid_path=invalid_path):
                write_registry(self.root, current_path=invalid_path)
                report = validate_registry(self.root)
                failures = [item["message"] for item in report["checks"] if not item["ok"]]
                self.assertFalse(report["ok"])
                self.assertTrue(
                    any(
                        marker in item
                        for item in failures
                        for marker in [
                            "instruction path is safe: current-status",
                            "instruction file exists: Harness/agents/missing.md",
                        ]
                    )
                )

    def test_registry_rejects_profile_swaps_and_malformed_action_lists(self) -> None:
        write_registry(self.root)
        config_path = self.root / "Harness/config/agents.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        data["subagent_roles"]["current-status"]["evidence_profile"] = "staged_commit"
        data["subagent_roles"]["commit-explainer"]["forbidden_actions"] = "commit"
        data["delegation_policy"]["common_forbidden_actions"] = {"commit": True}
        config_path.write_text(json.dumps(data), encoding="utf-8")

        report = validate_registry(self.root)
        failures = [item["message"] for item in report["checks"] if not item["ok"]]

        self.assertFalse(report["ok"])
        self.assertTrue(any("evidence profile matches the required role: current-status" in item for item in failures))
        self.assertTrue(any("delegation policy mutation prohibitions are a string list" in item for item in failures))
        self.assertTrue(any("mutation prohibitions are a string list: commit-explainer" in item for item in failures))

    def test_registry_rejects_oversized_role_prompt(self) -> None:
        write_registry(self.root)
        (self.root / "Harness/agents/current-status.md").write_text("x" * 40_000, encoding="utf-8")

        report = validate_registry(self.root)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                not item["ok"] and "instruction file is bounded: current-status" in item["message"]
                for item in report["checks"]
            )
        )

    def test_current_status_packet_preserves_request_and_writes_nothing(self) -> None:
        write_registry(self.root)
        (self.root / "Harness/work/state.md").write_text(
            "# State\n\n## Current State\n- api_key = \"do-not-echo-this-value\"\n",
            encoding="utf-8",
        )
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

        request = "현재 상황을 근거별로 정리"
        report = build_packet(self.root, "current-status", request=request)
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

        self.assertTrue(report["ok"])
        self.assertEqual(request, report["evidence"]["request"])
        self.assertIn("Current Status", report["prompt"])
        self.assertNotIn("do-not-echo-this-value", report["prompt"])
        self.assertIn("[REDACTED potential sensitive value]", report["prompt"])
        self.assertFalse(report["writes_files"])
        self.assertEqual(before, after)

    def test_current_status_redacts_entire_private_key_block(self) -> None:
        write_registry(self.root)
        (self.root / "Harness/work/state.md").write_text(
            "# State\n\n## Current State\n"
            "-----BEGIN PRIVATE KEY-----\n"
            "private-key-body-that-must-not-leak\n"
            "-----END PRIVATE KEY-----\n"
            "- safe summary\n",
            encoding="utf-8",
        )

        report = build_packet(self.root, "current-status", request="summarize")

        self.assertTrue(report["ok"])
        self.assertNotIn("BEGIN PRIVATE KEY", report["prompt"])
        self.assertNotIn("private-key-body-that-must-not-leak", report["prompt"])
        self.assertNotIn("END PRIVATE KEY", report["prompt"])
        self.assertIn("[REDACTED potential sensitive value]", report["prompt"])

    def test_delegation_inputs_are_redacted_and_bounded(self) -> None:
        write_registry(self.root)
        request = "api_key = hidden-request-value\n" + ("x" * 5_000)
        verification = [f"check {index}" for index in range(25)]

        report = build_packet(
            self.root,
            "current-status",
            request=request,
            verification=verification,
        )

        bounds = report["evidence"]["input_bounds"]
        self.assertTrue(report["ok"])
        self.assertNotIn("hidden-request-value", report["prompt"])
        self.assertTrue(bounds["request_truncated"])
        self.assertGreaterEqual(bounds["request_sensitive_redactions"], 1)
        self.assertEqual(20, len(report["evidence"]["explicit_verification"]))
        self.assertEqual(5, bounds["verification"]["omitted_items"])

    def test_private_key_redaction_spans_verification_list_items(self) -> None:
        write_registry(self.root)
        verification = [
            "-----BEGIN PRIVATE KEY-----",
            "PRIVATE-BODY-MUST-NOT-LEAK",
            "-----END PRIVATE KEY-----",
        ]

        report = build_packet(
            self.root,
            "current-status",
            request="summarize",
            verification=verification,
        )

        self.assertTrue(report["ok"])
        self.assertNotIn("BEGIN PRIVATE KEY", report["prompt"])
        self.assertNotIn("PRIVATE-BODY-MUST-NOT-LEAK", report["prompt"])
        self.assertNotIn("END PRIVATE KEY", report["prompt"])
        self.assertEqual(3, report["evidence"]["input_bounds"]["verification"]["sensitive_redactions"])

    def test_private_key_redaction_spans_request_and_verification_fields(self) -> None:
        write_registry(self.root)

        report = build_packet(
            self.root,
            "current-status",
            request="-----BEGIN PRIVATE KEY-----",
            verification=["CROSS-FIELD-BODY-MUST-NOT-LEAK", "-----END PRIVATE KEY-----"],
        )

        self.assertTrue(report["ok"])
        self.assertNotIn("CROSS-FIELD-BODY-MUST-NOT-LEAK", report["prompt"])
        self.assertEqual(
            "[REDACTED potential sensitive value]",
            report["evidence"]["explicit_verification"][0],
        )

    def test_unterminated_input_private_key_fails_closed_before_context_collection(self) -> None:
        write_registry(self.root)
        fake_context = {
            "warnings": ["CROSS-SOURCE-BODY-MUST-NOT-LEAK", "-----END PRIVATE KEY-----"]
        }

        with patch.object(harness_subagent, "build_context", return_value=fake_context) as context_mock:
            report = build_packet(
                self.root,
                "current-status",
                request="-----BEGIN PRIVATE KEY-----",
                verification=["-----END PRIVATE KEY-----"],
            )

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertNotIn("CROSS-SOURCE-BODY-MUST-NOT-LEAK", report["prompt"])
        self.assertIn("evidence_omitted", report["evidence"])
        context_mock.assert_not_called()

    def test_private_key_marker_order_on_one_line_keeps_following_body_redacted(self) -> None:
        write_registry(self.root)

        report = build_packet(
            self.root,
            "current-status",
            request="summarize",
            verification=[
                "-----END PRIVATE KEY----- -----BEGIN PRIVATE KEY-----",
                "ORDERED-BODY-MUST-NOT-LEAK",
            ],
        )

        self.assertTrue(report["ok"])
        self.assertNotIn("ORDERED-BODY-MUST-NOT-LEAK", report["prompt"])

    def test_private_key_body_redaction_does_not_preserve_diff_prefix(self) -> None:
        write_registry(self.root)

        report = build_packet(
            self.root,
            "current-status",
            request="summarize",
            verification=[
                "-----BEGIN PRIVATE KEY-----",
                "+PRIVATE-BODY-MUST-NOT-LEAK",
                "-----END PRIVATE KEY-----",
            ],
        )

        self.assertTrue(report["ok"])
        self.assertNotIn("+PRIVATE", report["prompt"])
        self.assertEqual(
            "[REDACTED potential sensitive value]",
            report["evidence"]["explicit_verification"][1],
        )

    def test_private_key_redaction_spans_nested_context_list_items(self) -> None:
        write_registry(self.root)
        fake_context = {
            "project": {},
            "active_task": "",
            "recommended_first_reads": [],
            "next_items": [],
            "cycle_policy": {"iteration_status": None},
            "warnings": [
                "-----BEGIN PRIVATE KEY-----",
                "CONTEXT-BODY-MUST-NOT-LEAK",
                "-----END PRIVATE KEY-----",
            ],
        }

        with patch.object(harness_subagent, "build_context", return_value=fake_context):
            report = build_packet(self.root, "current-status", request="summarize")

        self.assertTrue(report["ok"])
        self.assertNotIn("BEGIN PRIVATE KEY", report["prompt"])
        self.assertNotIn("CONTEXT-BODY-MUST-NOT-LEAK", report["prompt"])
        self.assertNotIn("END PRIVATE KEY", report["prompt"])
        self.assertEqual(3, report["evidence"]["context_bounds"]["sensitive_redactions"])

    def test_commit_packet_is_not_ready_without_staged_changes(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("unstaged\n", encoding="utf-8", newline="\n")
        (self.root / "untracked.txt").write_text("outside commit\n", encoding="utf-8")

        report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertFalse(report["evidence"]["git"]["staged"]["has_changes"])
        self.assertTrue(report["evidence"]["git"]["unstaged"]["has_changes"])
        self.assertIn("untracked.txt", report["evidence"]["git"]["untracked"]["sample"])
        self.assertTrue(any("no staged changes" in item for item in report["warnings"]))

    def test_commit_packet_separates_scope_and_redacts_bounded_patch(self) -> None:
        write_registry(self.root)
        self._init_git()
        staged_text = "api_key = \"super-secret-value\"\n" + "\n".join(f"staged {index}" for index in range(250)) + "\n"
        tracked = self.root / "tracked.txt"
        tracked.write_text(staged_text, encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        tracked.write_text(staged_text + "unstaged tail\n", encoding="utf-8", newline="\n")
        (self.root / "untracked.txt").write_text("outside commit\n", encoding="utf-8")

        report = build_packet(
            self.root,
            "commit-explainer",
            request="prepare commit",
            verification=["python tests.py: passed"],
            include_staged_patch=True,
            max_patch_chars=1024,
        )
        staged = report["evidence"]["git"]["staged"]
        unstaged = report["evidence"]["git"]["unstaged"]

        self.assertTrue(report["ready"], report["warnings"])
        self.assertTrue(staged["has_changes"])
        self.assertTrue(unstaged["has_changes"])
        self.assertIn("tracked.txt", staged["paths"])
        self.assertIn("tracked.txt", unstaged["paths"])
        self.assertIn("[REDACTED potential sensitive value]", staged["patch_excerpt"])
        self.assertNotIn("super-secret-value", staged["patch_excerpt"])
        self.assertNotIn("unstaged tail", staged["patch_excerpt"])
        self.assertTrue(staged["patch_truncated"])
        self.assertEqual(["python tests.py: passed"], report["evidence"]["explicit_verification"])

    def test_git_evidence_hashes_staged_snapshot_without_including_patch_by_default(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("staged\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)

        evidence = collect_git_evidence(self.root)

        self.assertTrue(evidence["staged"]["has_changes"])
        self.assertEqual(64, len(evidence["staged"]["snapshot_sha256"]))
        self.assertEqual(
            "matching start/end ref identity, staged-raw, and porcelain-v1 -z digests",
            evidence["staged"]["snapshot_basis"],
        )
        self.assertEqual(0, evidence["staged"]["patch_bytes_read"])
        self.assertFalse(evidence["staged"]["patch_included"])
        self.assertEqual("", evidence["staged"]["patch_excerpt"])

    def test_redacted_patch_is_rebounded_after_placeholder_expansion(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("password=x\n" * 60, encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)

        evidence = collect_git_evidence(self.root, include_staged_patch=True, max_patch_chars=1024)
        staged = evidence["staged"]

        self.assertLess(staged["patch_bytes_read"], 1024)
        self.assertLessEqual(len(staged["patch_excerpt"]), 1024)
        self.assertTrue(staged["patch_truncated"])
        self.assertNotIn("password=x", staged["patch_excerpt"])

    def test_library_api_rejects_unbounded_patch_limits(self) -> None:
        write_registry(self.root)
        self._init_git()

        for invalid in [-1, 0, 1023, 262_145, True, "4096"]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    collect_git_evidence(self.root, max_patch_chars=invalid)

    def test_commit_packet_is_not_ready_when_staged_scope_exceeds_sample(self) -> None:
        write_registry(self.root)
        self._init_git()
        for index in range(257):
            (self.root / f"staged-{index:03d}.txt").write_text(f"{index}\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "staged-*.txt").returncode)

        report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertGreater(report["evidence"]["git"]["staged"]["paths_omitted"], 0)
        self.assertTrue(any("staged path scope exceeds" in item for item in report["warnings"]))
        snapshot = report["evidence"]["git"]["snapshot_id"]
        expanded = build_packet(self.root, "commit-explainer", max_staged_paths=512, expected_snapshot=snapshot)
        self.assertTrue(expanded["ready"], expanded["warnings"])
        self.assertTrue(expanded["evidence"]["git"]["staged"]["path_listing_complete"])
        (self.root / "staged-000.txt").write_text("changed\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "staged-000.txt").returncode)
        stale = build_packet(self.root, "commit-explainer", max_staged_paths=512, expected_snapshot=snapshot)
        self.assertFalse(stale["ready"])
        self.assertTrue(any("snapshot differs" in item for item in stale["warnings"]))

    def test_staged_path_bound_is_validated_independently(self) -> None:
        for invalid in [0, -1, 4097, True, "256"]:
            with self.assertRaises(ValueError):
                collect_git_evidence(self.root, max_staged_paths=invalid)

    def test_large_path_sample_also_has_an_aggregate_byte_bound(self) -> None:
        with patch("harness_subagent.subprocess.Popen") as popen:
            process = popen.return_value
            process.stdout = io.BytesIO((b"a" * 65_000 + b"\0") * 10)
            process.communicate.return_value = (b"", b"")
            process.returncode = 0
            with patch("harness_subagent.resolve_git_executable", return_value="git"):
                report = harness_subagent._run_git_tokens(self.root, ["diff"], sample_limit=4096)
        self.assertTrue(report["ok"])
        self.assertEqual(10, report["count"])
        self.assertEqual(6, report["omitted"])
        self.assertLessEqual(report["sample_bytes"], harness_subagent.MAX_PATH_SAMPLE_BYTES)

    def test_recheck_routes_use_the_platform_safe_launcher(self) -> None:
        write_registry(self.root)
        self._init_git()
        for role in ["current-status", "commit-explainer"]:
            report = build_packet(self.root, role)
            command = report["evidence"]["recheck_route"]["command"]
            self.assertNotIn("harness.cmd", command)
            self.assertIn("harness.ps1" if os.name == "nt" else "harness.sh", command)

    def test_commit_packet_rejects_a_staged_snapshot_race(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("staged\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        original = harness_subagent._run_git_digest
        staged_digest_calls = 0

        def race_digest(root, args):
            nonlocal staged_digest_calls
            result = original(root, args)
            if args[:3] == ["diff", "--cached", "--raw"]:
                staged_digest_calls += 1
                if staged_digest_calls == 2 and result["ok"]:
                    result = {**result, "sha256": "0" * 64}
            return result

        with patch.object(harness_subagent, "_run_git_digest", side_effect=race_digest):
            report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertFalse(report["evidence"]["git"]["snapshot_consistent"])
        self.assertTrue(any("git state changed" in item for item in report["warnings"]))

    def test_commit_packet_rejects_a_ref_snapshot_race(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("staged\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        original = harness_subagent._collect_ref_identity
        ref_calls = 0

        def race_ref(root):
            nonlocal ref_calls
            result = original(root)
            ref_calls += 1
            if ref_calls == 2 and result["ok"]:
                result = {**result, "identity": {**result["identity"], "branch": "simulated-other-branch"}}
            return result

        with patch.object(harness_subagent, "_collect_ref_identity", side_effect=race_ref):
            report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertFalse(report["evidence"]["git"]["snapshot_consistent"])

    def test_commit_packet_rejects_an_unstaged_evidence_race(self) -> None:
        write_registry(self.root)
        self._init_git()
        tracked = self.root / "tracked.txt"
        tracked.write_text("staged\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        tracked.write_text("staged\nunstaged\n", encoding="utf-8", newline="\n")
        original = harness_subagent._run_git_prefix
        stat_calls = 0
        check_calls = 0

        def race_unstaged_evidence(root, args, **kwargs):
            nonlocal stat_calls, check_calls
            result = original(root, args, **kwargs)
            if args == ["diff", "--shortstat", "--no-ext-diff", "--no-textconv"]:
                stat_calls += 1
                if stat_calls == 2:
                    result = {**result, "stdout": result["stdout"] + " simulated-change"}
            if args == ["diff", "--check", "--no-ext-diff", "--no-textconv"]:
                check_calls += 1
                if check_calls == 2:
                    result = {**result, "stdout": result["stdout"] + "simulated-change"}
            return result

        with patch.object(harness_subagent, "_run_git_prefix", side_effect=race_unstaged_evidence):
            report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertFalse(report["evidence"]["git"]["snapshot_consistent"])

    def test_commit_packet_supports_an_unborn_head(self) -> None:
        write_registry(self.root)
        if not shutil.which("git"):
            self.skipTest("git is not available")
        self.assertEqual(0, self._git("init").returncode)
        self.assertEqual(0, self._git("config", "user.email", "harness@example.invalid").returncode)
        self.assertEqual(0, self._git("config", "user.name", "Harness Tests").returncode)
        (self.root / "initial.txt").write_text("initial\n", encoding="utf-8")
        self.assertEqual(0, self._git("add", "initial.txt").returncode)

        report = build_packet(self.root, "commit-explainer", request="prepare initial commit")

        self.assertTrue(report["ok"])
        self.assertTrue(report["ready"], report["warnings"])
        self.assertTrue(report["evidence"]["git"]["unborn_head"])
        self.assertEqual("unborn", report["evidence"]["git"]["head"])

    def test_commit_packet_propagates_git_command_failures(self) -> None:
        write_registry(self.root)
        self._init_git()
        (self.root / "tracked.txt").write_text("staged\n", encoding="utf-8", newline="\n")
        self.assertEqual(0, self._git("add", "tracked.txt").returncode)
        original = harness_subagent._run_git_prefix

        def fail_staged_stat(root, args, **kwargs):
            if args[:3] == ["diff", "--cached", "--shortstat"]:
                return {"ok": False, "exit_code": 2, "stdout": "", "stderr": "simulated failure", "truncated": False}
            return original(root, args, **kwargs)

        with patch.object(harness_subagent, "_run_git_prefix", side_effect=fail_staged_stat):
            report = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertTrue(report["ok"])
        self.assertFalse(report["ready"])
        self.assertIn("staged_stat", report["evidence"]["git"]["command_errors"])

    def test_git_evidence_preserves_unicode_space_and_rename_paths(self) -> None:
        write_registry(self.root)
        self._init_git()
        old_name = "기존 이름.txt"
        new_name = "새 이름 변경.txt"
        (self.root / old_name).write_text("rename me\n", encoding="utf-8")
        self.assertEqual(0, self._git("add", old_name).returncode)
        self.assertEqual(0, self._git("commit", "-m", "Add rename fixture").returncode)
        self.assertEqual(0, self._git("mv", old_name, new_name).returncode)

        evidence = collect_git_evidence(self.root)

        self.assertTrue(evidence["commands_ok"], evidence["command_errors"])
        self.assertIn(new_name, evidence["staged"]["paths"])
        self.assertTrue(any(new_name in item for item in evidence["status"]["sample"]))

    def test_current_status_packet_does_not_refresh_git_index_or_create_memory_db(self) -> None:
        write_registry(self.root)
        self._init_git()
        index_path = self.root / ".git/index"
        before_bytes = index_path.read_bytes()
        before_mtime = index_path.stat().st_mtime_ns
        memory_candidates = [
            self.root / "Harness/data/harness.sqlite",
            self.root / "Harness/data/harness.sqlite-wal",
            self.root / "Harness/data/harness.sqlite-shm",
        ]
        self.assertFalse(any(path.exists() for path in memory_candidates))

        report = build_packet(self.root, "current-status", request="summarize current state")

        self.assertTrue(report["ok"])
        self.assertEqual(before_bytes, index_path.read_bytes())
        self.assertEqual(before_mtime, index_path.stat().st_mtime_ns)
        self.assertFalse(any(path.exists() for path in memory_candidates))

    def test_packets_route_rechecks_through_the_safe_wrapper(self) -> None:
        write_registry(self.root)
        self._init_git()

        current = build_packet(self.root, "current-status", request="summarize")
        commit = build_packet(self.root, "commit-explainer", request="prepare commit")

        self.assertIn("subagent --role current-status", current["evidence"]["recheck_route"]["command"])
        self.assertIn("subagent --role commit-explainer", commit["evidence"]["recheck_route"]["command"])
        self.assertEqual("primary_agent", current["evidence"]["recheck_route"]["owner"])
        self.assertEqual("primary_agent", commit["evidence"]["recheck_route"]["owner"])
