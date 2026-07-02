from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from _harness_test_base import HarnessBaseTestCase
from harness_local_gate import build_gate, clean_python_caches


class LocalGateTests(HarnessBaseTestCase):
    def test_clean_python_caches_removes_only_harness_generated_python_cache(self) -> None:
        cache_dir = self.root / "Harness/scripts/tools/__pycache__"
        cache_dir.mkdir(parents=True)
        pyc = cache_dir / "tool.cpython-312.pyc"
        pyc.write_bytes(b"cache")
        outside = self.root / "__pycache__"
        outside.mkdir()
        outside_pyc = outside / "outside.pyc"
        outside_pyc.write_bytes(b"outside")

        report = clean_python_caches(self.root)

        self.assertTrue(report["ok"])
        self.assertFalse(cache_dir.exists())
        self.assertTrue(outside_pyc.exists())

    def test_build_gate_runs_expected_steps(self) -> None:
        commands: list[list[str]] = []

        def fake_run(root: Path, command: list[str]) -> dict:
            commands.append(command)
            return {"ok": True, "returncode": 0, "command": " ".join(command), "output": ""}

        with patch("harness_local_gate.run_command", side_effect=fake_run):
            report = build_gate(self.root, release=True, skip_tests=False)

        self.assertTrue(report["ok"])
        self.assertEqual(
            [step["name"] for step in report["steps"]],
            ["tool_tests", "clean_python_caches", "harness_verify_all", "strict_release_check", "diff_check", "diff_stat"],
        )
        self.assertTrue(any("harness_verify_all.py" in " ".join(command) for command in commands))
        self.assertTrue(any("harness_release_check.py" in " ".join(command) for command in commands))
        self.assertTrue(any(command == ["git", "diff", "--check"] for command in commands))
