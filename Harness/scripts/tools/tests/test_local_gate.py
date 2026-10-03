from __future__ import annotations

import shutil
import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

from _harness_test_base import HarnessBaseTestCase
from harness_local_gate import build_gate, build_git_steps, clean_python_caches, inspect_python_caches, run_command


class LocalGateTests(HarnessBaseTestCase):
    def test_cache_cleanup_refuses_linked_harness_root(self):
        harness = self.root / "Harness"
        target = self.root / "preserved-harness"
        harness.rename(target)
        cache = target / "__pycache__"
        cache.mkdir()
        marker = cache / "preserved.pyc"
        marker.write_bytes(b"preserve")
        try:
            harness.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlink permission unavailable")
        report = clean_python_caches(self.root)
        self.assertFalse(report["ok"])
        self.assertEqual([], report["removed"])
        self.assertTrue(marker.is_file())

    def test_foreign_index_cannot_hide_staged_whitespace(self) -> None:
        self._init_git()
        target = self.root / "staged.txt"
        target.write_text("bad whitespace   \n", encoding="utf-8")
        self._git("add", "staged.txt")
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(self.root / "foreign-index")}):
            steps = self._steps_by_name(build_git_steps(self.root))
        self.assertFalse(steps["staged_diff_check"]["ok"])

    def test_rename_status_is_one_record_and_unicode_paths_survive(self) -> None:
        from harness_diff_guard import run_git_status, changed_path_from_status
        from harness_memory_review import git_changed_paths
        self._init_git()
        self._git("mv", "HARNESS.md", "새 규칙.md")
        steps = self._steps_by_name(build_git_steps(self.root))
        records = steps["git_status"]["records"]
        self.assertEqual(1, len(records))
        self.assertEqual("HARNESS.md", records[0]["original_path"])
        ok, lines = run_git_status(self.root)
        self.assertTrue(ok)
        self.assertEqual(["새 규칙.md"], [changed_path_from_status(line) for line in lines])
        self.assertEqual(["새 규칙.md"], git_changed_paths(self.root)["paths"])

    def test_status_parser_preserves_literal_arrow_and_newline(self) -> None:
        from harness_common import parse_git_status_z
        from harness_diff_guard import changed_path_from_status
        import json
        path = "Source/a -> b\n.cpp"
        entries = parse_git_status_z(" M " + path + "\0")
        self.assertEqual(path, entries[0]["path"])
        self.assertEqual(path, changed_path_from_status(" M " + json.dumps(path)))
        with self.assertRaises(ValueError):
            parse_git_status_z("R  dest\0")

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(f"git {' '.join(args)} failed: {completed.stdout}\n{completed.stderr}")
        return completed

    def _init_git(self) -> str:
        if not shutil.which("git"):
            self.skipTest("git is unavailable")
        self._git("init")
        self._git("config", "user.email", "harness@example.invalid")
        self._git("config", "user.name", "Harness Test")
        self._git("config", "core.autocrlf", "false")
        self._git("config", "core.quotePath", "false")
        self._git("add", "--all")
        self._git("commit", "-m", "baseline")
        return self._git("branch", "--show-current").stdout.strip()

    @staticmethod
    def _steps_by_name(steps: list[dict]) -> dict[str, dict]:
        return {step["name"]: step for step in steps}

    def test_clean_python_caches_removes_only_harness_generated_python_cache(self) -> None:
        cache_dir = self.root / "Harness/scripts/tools/__pycache__"
        cache_dir.mkdir(parents=True)
        pyc = cache_dir / "tool.cpython-312.pyc"
        pyc.write_bytes(b"cache")
        pyc.chmod(stat.S_IREAD)
        cache_dir.chmod(stat.S_IREAD)
        outside = self.root / "__pycache__"
        outside.mkdir()
        outside_pyc = outside / "outside.pyc"
        outside_pyc.write_bytes(b"outside")

        report = clean_python_caches(self.root)

        self.assertTrue(report["ok"])
        self.assertFalse(cache_dir.exists())
        self.assertTrue(outside_pyc.exists())

    def test_default_gate_reports_cache_without_deleting_it(self) -> None:
        cache_dir = self.root / "Harness/scripts/tools/__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "tool.pyc").write_bytes(b"cache")

        successful = {"ok": True, "executed": True, "returncode": 0, "command": "test", "output": ""}
        git_steps = [{"name": "git_repository", "scope": "repository", **successful}]
        with patch("harness_local_gate.run_command", return_value=successful), patch(
            "harness_local_gate.build_git_steps", return_value=git_steps
        ), patch("harness_local_gate.build_memory_review", return_value={"ok": True}):
            report = build_gate(self.root, skip_tests=True)

        cleanup = next(step for step in report["steps"] if step["name"] == "clean_python_caches")
        self.assertTrue(report["ok"])
        self.assertTrue(cleanup["skipped"])
        self.assertFalse(cleanup["executed"])
        self.assertEqual(1, cleanup["found_count"])
        self.assertTrue(cache_dir.exists())

    def test_cache_cleanup_ignores_managed_python_runtime(self) -> None:
        runtime_cache = self.root / "Harness/.runtime/linux-x86_64/python/lib/__pycache__"
        runtime_cache.mkdir(parents=True)
        runtime_pyc = runtime_cache / "runtime.pyc"
        runtime_pyc.write_bytes(b"managed runtime")

        inventory = inspect_python_caches(self.root)
        report = clean_python_caches(self.root)

        self.assertEqual(0, inventory["found_count"])
        self.assertTrue(report["ok"])
        self.assertTrue(runtime_pyc.exists())

    def test_explicit_cache_cleanup_refuses_outside_root_symlink(self) -> None:
        outside = self.root / "outside"
        outside_cache = outside / "__pycache__"
        outside_cache.mkdir(parents=True)
        outside_pyc = outside_cache / "keep.pyc"
        outside_pyc.write_bytes(b"outside")
        link = self.root / "Harness/scripts/tools/external-link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")

        inventory = inspect_python_caches(self.root)
        report = clean_python_caches(self.root)

        self.assertIn("Harness/scripts/tools/external-link", inventory["blocked_links"])
        self.assertFalse(report["ok"])
        self.assertTrue(outside_pyc.exists())

    def test_run_command_reports_missing_executable_instead_of_crashing(self) -> None:
        result = run_command(self.root, ["definitely_not_a_real_executable_12345", "--version"])
        self.assertFalse(result["ok"])
        self.assertEqual(-1, result["returncode"])
        self.assertIn("command could not start", result["output"])

    def test_build_gate_runs_expected_steps(self) -> None:
        commands: list[list[str]] = []

        def fake_run(root: Path, command: list[str]) -> dict:
            commands.append(command)
            return {"ok": True, "executed": True, "returncode": 0, "command": " ".join(command), "output": ""}

        fake_memory_review = {"ok": True, "review_recommended": True, "suggestions": [{"candidate": "project rule", "reason": "agent operating rule changed", "example_path": "HARNESS.md"}]}
        fake_git_steps = [
            {"name": "git_repository", "ok": True, "executed": True, "scope": "repository"},
            {"name": "git_status", "ok": True, "executed": True, "scope": "working_tree", "untracked": []},
            {"name": "conflict_check", "ok": True, "executed": True, "scope": "index"},
            {"name": "diff_check", "ok": True, "executed": True, "scope": "unstaged"},
            {"name": "staged_diff_check", "ok": True, "executed": True, "scope": "staged"},
            {"name": "diff_stat", "ok": True, "executed": True, "scope": "unstaged"},
            {"name": "staged_diff_stat", "ok": True, "executed": True, "scope": "staged"},
        ]

        with patch("harness_local_gate.run_command", side_effect=fake_run), patch(
            "harness_local_gate.build_memory_review", return_value=fake_memory_review
        ), patch("harness_local_gate.build_git_steps", return_value=fake_git_steps):
            report = build_gate(self.root, release=True, skip_tests=False)

        self.assertTrue(report["ok"])
        self.assertEqual(
            [step["name"] for step in report["steps"]],
            [
                "tool_tests",
                "clean_python_caches",
                "harness_verify_all",
                "strict_release_check",
                "memory_review",
                "git_repository",
                "git_status",
                "conflict_check",
                "diff_check",
                "staged_diff_check",
                "diff_stat",
                "staged_diff_stat",
            ],
        )
        self.assertTrue(any("harness_verify_all.py" in " ".join(command) for command in commands))
        self.assertTrue(any("harness_release_check.py" in " ".join(command) for command in commands))
        self.assertTrue(all("scope" in step and "executed" in step for step in report["steps"]))

    def test_git_steps_catch_staged_trailing_whitespace(self) -> None:
        self._init_git()
        (self.root / "staged.txt").write_text("bad trailing spaces  \n", encoding="utf-8")
        self._git("add", "staged.txt")

        steps = self._steps_by_name(build_git_steps(self.root))

        self.assertTrue(steps["diff_check"]["ok"])
        self.assertFalse(steps["staged_diff_check"]["ok"])
        self.assertEqual("staged", steps["staged_diff_check"]["scope"])

    def test_git_steps_catch_unstaged_trailing_whitespace(self) -> None:
        self._init_git()
        (self.root / "HARNESS.md").write_text("# Harness  \n", encoding="utf-8")

        steps = self._steps_by_name(build_git_steps(self.root))

        self.assertFalse(steps["diff_check"]["ok"])
        self.assertTrue(steps["staged_diff_check"]["ok"])

    def test_git_steps_check_both_layers_of_partially_staged_file(self) -> None:
        self._init_git()
        path = self.root / "layered.txt"
        path.write_text("base\n", encoding="utf-8")
        self._git("add", "layered.txt")
        self._git("commit", "-m", "add layered file")
        path.write_text("staged defect  \n", encoding="utf-8")
        self._git("add", "layered.txt")
        path.write_text("unstaged defect\t\n", encoding="utf-8")

        steps = self._steps_by_name(build_git_steps(self.root))

        self.assertFalse(steps["staged_diff_check"]["ok"])
        self.assertFalse(steps["diff_check"]["ok"])

    def test_git_steps_report_untracked_utf8_path_without_failing(self) -> None:
        self._init_git()
        (self.root / "한글 file.txt").write_text("untracked\n", encoding="utf-8")

        steps = self._steps_by_name(build_git_steps(self.root))

        self.assertTrue(steps["git_status"]["ok"])
        self.assertEqual(["한글 file.txt"], steps["git_status"]["untracked"])

    def test_git_steps_fail_for_unmerged_index(self) -> None:
        base_branch = self._init_git()
        path = self.root / "conflict.txt"
        path.write_text("base\n", encoding="utf-8")
        self._git("add", "conflict.txt")
        self._git("commit", "-m", "add conflict fixture")
        self._git("checkout", "-b", "other")
        path.write_text("other\n", encoding="utf-8")
        self._git("commit", "-am", "other change")
        self._git("checkout", base_branch)
        path.write_text("main\n", encoding="utf-8")
        self._git("commit", "-am", "main change")
        merge = self._git("merge", "other", check=False)
        self.assertNotEqual(0, merge.returncode)

        steps = self._steps_by_name(build_git_steps(self.root))

        self.assertFalse(steps["conflict_check"]["ok"])
        self.assertEqual(["conflict.txt"], steps["conflict_check"]["conflicts"])

    def test_git_steps_fail_explicitly_outside_repository(self) -> None:
        steps = build_git_steps(self.root)

        self.assertFalse(steps[0]["ok"])
        self.assertEqual("git_repository", steps[0]["name"])
        self.assertTrue(all(step.get("skipped") for step in steps[1:]))
