"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class FieldCheckTests(HarnessBaseTestCase):
    def test_field_check_no_branch_mode_does_not_assume_remote_alignment(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text("# Agent Field Guide\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")

        def fake_git(_root: Path, args: list[str]) -> dict:
            if args == ["status", "--short", "--branch"]:
                return {"ok": True, "stdout": "## main...origin/main", "stderr": ""}
            if args == ["worktree", "list", "--porcelain"]:
                return {"ok": True, "stdout": f"worktree {self.root.as_posix()}\nHEAD abc\nbranch refs/heads/main", "stderr": ""}
            self.fail(f"unexpected git command: {args}")

        with patch("harness_field_check._run_git", side_effect=fake_git):
            report = build_field_report(self.root)

        self.assertTrue(report["ok"])
        self.assertEqual("single_checkout", report["worktrees"]["checkout_mode"])
        self.assertFalse(report["worktrees"]["remote_alignment"]["enabled"])
        self.assertIsNone(report["worktrees"]["remote_alignment"]["aligned"])
    def test_field_check_reports_requested_branch_alignment(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text("# Agent Field Guide\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")

        def fake_git(_root: Path, args: list[str]) -> dict:
            if args == ["status", "--short", "--branch"]:
                return {"ok": True, "stdout": "## main...origin/main", "stderr": ""}
            if args == ["worktree", "list", "--porcelain"]:
                return {"ok": True, "stdout": f"worktree {self.root.as_posix()}\nHEAD abc\nbranch refs/heads/main", "stderr": ""}
            if args == ["ls-remote", "--heads", "origin", "main", "feature/login"]:
                return {
                    "ok": True,
                    "stdout": "abc\trefs/heads/main\nabc\trefs/heads/feature/login\n",
                    "stderr": "",
                }
            self.fail(f"unexpected git command: {args}")

        with patch("harness_field_check._run_git", side_effect=fake_git):
            report = build_field_report(self.root, branches=["main", "feature/login"])

        self.assertTrue(report["worktrees"]["remote_alignment"]["aligned"])
        self.assertEqual(["abc"], report["worktrees"]["remote_alignment"]["commits"])
        self.assertTrue(any(item["message"] == "requested_remote_refs_aligned" for item in report["notes"]))
    def test_field_check_reports_unreal_script_wrapper_command(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text("# Agent Field Guide\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")
        unreal_scripts = self.root / "Harness/scripts/unreal"
        unreal_scripts.mkdir(parents=True)
        (unreal_scripts / "verify_level.py").write_text("import unreal as ue\n", encoding="utf-8")
        report = build_field_report(self.root)
        self.assertTrue(report["ok"])
        self.assertEqual(1, report["unreal_scripts"]["unreal_import_count"])
        self.assertTrue(any("harness_unreal_script.py" in item.get("command", "") for item in report["notes"]))
    def test_field_check_requires_field_guide(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        report = build_field_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["message"] == "field_guide_missing" for item in report["errors"]))
    def test_field_check_warns_about_unreal_script_accumulation(self) -> None:
        unreal = self.root / "Harness/scripts/unreal"
        unreal.mkdir(parents=True)
        for index in range(25):
            (unreal / f"capture_sample_{index}.py").write_text("VALUE = 1\n", encoding="utf-8")
        report = build_field_report(self.root)
        self.assertFalse(any("unreal_script_accumulation" in item["message"] for item in report["warnings"]))
        (unreal / "capture_sample_extra.py").write_text("VALUE = 1\n", encoding="utf-8")
        report = build_field_report(self.root)
        matches = [item for item in report["warnings"] if "unreal_script_accumulation" in item["message"]]
        self.assertEqual(1, len(matches))
        self.assertIn("26", matches[0]["message"])
    def test_field_check_warns_for_nested_harness_root(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text("# Agent Field Guide\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")
        nested = self.root / "TemplateCopy"
        (nested / "Harness").mkdir(parents=True)
        (nested / "HARNESS.md").write_text("# Harness\n", encoding="utf-8")
        report = build_field_report(self.root)
        self.assertTrue(any(item["message"].startswith("nested_harness_root_detected") for item in report["warnings"]))
    def test_field_check_warns_for_text_encoding_artifacts(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text(
            "# Agent Field Guide\n\n- Broken text abc??def\n",
            encoding="utf-8",
        )
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")
        report = build_field_report(self.root)
        self.assertTrue(any(item["message"] == "suspicious_text_encoding_artifact" for item in report["warnings"]))
    def test_field_check_warns_when_requested_branches_diverge(self) -> None:
        (self.root / "Harness/docs").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/AgentFieldGuide.md").write_text("# Agent Field Guide\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("See AgentFieldGuide.md\n", encoding="utf-8")

        def fake_git(_root: Path, args: list[str]) -> dict:
            if args == ["status", "--short", "--branch"]:
                return {"ok": True, "stdout": "## main...origin/main", "stderr": ""}
            if args == ["worktree", "list", "--porcelain"]:
                return {"ok": True, "stdout": f"worktree {self.root.as_posix()}\nHEAD abc\nbranch refs/heads/main", "stderr": ""}
            if args == ["ls-remote", "--heads", "origin", "main", "release/1.2"]:
                return {
                    "ok": True,
                    "stdout": "abc\trefs/heads/main\ndef\trefs/heads/release/1.2\n",
                    "stderr": "",
                }
            self.fail(f"unexpected git command: {args}")

        with patch("harness_field_check._run_git", side_effect=fake_git):
            report = build_field_report(self.root, branches=["main", "release/1.2"])

        self.assertFalse(report["worktrees"]["remote_alignment"]["aligned"])
        self.assertTrue(any(item["message"] == "requested_remote_refs_diverged" for item in report["warnings"]))
