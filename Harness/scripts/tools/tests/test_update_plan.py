"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class UpdatePlanTests(HarnessBaseTestCase):
    def test_migration_audit_accepts_direct_harness_directory(self) -> None:
        report = migration_audit(self.root / "Harness")
        self.assertTrue(report["ok"])
        self.assertTrue(report["layout"]["target_is_harness_dir"])
        self.assertEqual("single", report["layout"]["kind"])
        self.assertTrue(any(item["level"] == "info" for item in report["findings"]))

    def test_migration_audit_reports_single_layout_and_incomplete_build(self) -> None:
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({"project_name": "Demo", "template_mode": False, "build": {}}),
            encoding="utf-8",
        )
        report = migration_audit(self.root)
        self.assertEqual("single", report["layout"]["kind"])
        self.assertTrue(report["ok"])
        self.assertIn("Harness/config/project.json", report["preserve"])
        self.assertTrue(any("build config is incomplete" in item["message"] for item in report["findings"]))
        self.assertFalse(any("memory shards" in item for item in report["preserve"]))
        (self.root / "Harness/data/memory").mkdir(parents=True)
        (self.root / "Harness/data/memory/2026-07-01.jsonl").write_text('{"id": "example"}\n', encoding="utf-8")
        report = migration_audit(self.root)
        self.assertTrue(any("memory shards" in item for item in report["preserve"]))
    def test_update_actions_reject_paths_that_escape_roots(self) -> None:
        template = self.root / "template"
        target = self.root / "target"
        stage = self.root / "review"
        template.mkdir()
        (target / "Harness").mkdir(parents=True)
        escaped = self.root / "escaped.txt"
        escaped.write_text("outside\n", encoding="utf-8")
        add_plan = {"actions": [{"path": "../escaped.txt", "action": "add"}]}
        review_plan = {"actions": [{"path": "../escaped.txt", "action": "replace_review"}]}
        with self.assertRaises(ValueError):
            apply_missing_files(template, target, add_plan)
        with self.assertRaises(ValueError):
            stage_review_files(template, stage, review_plan, target=target)
        self.assertEqual("outside\n", escaped.read_text(encoding="utf-8"))
    def test_update_apply_preflights_all_sources_without_partial_copy(self) -> None:
        template = self.root / "atomic-template"
        target = self.root / "atomic-target"
        template.mkdir()
        (target / "Harness").mkdir(parents=True)
        (template / "one.txt").write_text("one\n", encoding="utf-8")
        plan = {"actions": [{"path": "one.txt", "action": "add"}, {"path": "missing.txt", "action": "add"}]}
        with self.assertRaises(FileNotFoundError):
            apply_missing_files(template, target, plan)
        self.assertFalse((target / "one.txt").exists())
    def test_update_apply_requires_existing_harness_target(self) -> None:
        missing_target = self.root / "typo-target"
        plan = build_update_plan(self.root, missing_target)
        with self.assertRaises(ValueError):
            apply_missing_files(self.root, missing_target, plan)
        self.assertFalse(missing_target.exists())
    def test_update_plan_preserves_project_data_and_stages_review_files(self) -> None:
        template = self.root / "new-template"
        target = self.root / "old-project"
        for base in [template, target]:
            (base / "Harness/config").mkdir(parents=True)
            (base / "Harness/docs").mkdir(parents=True)
            (base / "Harness/scripts/tools").mkdir(parents=True)
        for name in ["HARNESS.md", "AGENTS.md", "CLAUDE.md"]:
            (template / name).write_text(f"new {name}\n", encoding="utf-8")
        (template / "Harness/README.md").write_text("new readme\n", encoding="utf-8")
        (template / "Harness/docs/template").mkdir(parents=True, exist_ok=True)
        (template / "Harness/docs/template/setup.md").write_text("new setup\n", encoding="utf-8")
        (template / "Harness/docs/template/changelog.md").write_text("new changelog\n", encoding="utf-8")
        (template / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        (template / "Harness/config/docs.json").write_text('{"doc_roots": []}\n', encoding="utf-8")
        (template / "Harness/docs/Guide.md").write_text("new guide\n", encoding="utf-8")
        (template / "Harness/Progress.md.bak").write_text("template backup\n", encoding="utf-8")
        (template / "Harness/scripts/tools/standard.py").write_text("NEW = 1\n", encoding="utf-8")
        (target / "HARNESS.md").write_text("project rules\n", encoding="utf-8")
        (target / "Harness/config/project.json").write_text('{"project_name": "KeepMe"}\n', encoding="utf-8")
        (target / "Harness/docs/Guide.md").write_text("project knowledge\n", encoding="utf-8")
        (target / "Harness/Progress.md.bak").write_text("old backup\n", encoding="utf-8")
        (target / "Harness/scripts/tools/standard.py").write_text("OLD = 1\n", encoding="utf-8")
        (target / "Harness/scripts/tools/custom.py").write_text("CUSTOM = 1\n", encoding="utf-8")
        plan = build_update_plan(template, target)
        actions = {item["path"]: item["action"] for item in plan["actions"]}
        self.assertEqual("preserve", actions["Harness/config/project.json"])
        self.assertEqual("preserve", actions["Harness/docs/Guide.md"])
        self.assertEqual("add", actions["Harness/docs/template/setup.md"])
        self.assertEqual("merge_review", actions["HARNESS.md"])
        self.assertEqual("replace_review", actions["Harness/scripts/tools/standard.py"])
        self.assertEqual("replace_review", actions["Harness/Progress.md.bak"])
        self.assertIn("Harness/scripts/tools/custom.py", plan["custom_tools"])
        copied = apply_missing_files(template, target, plan)
        self.assertIn("CLAUDE.md", copied)
        self.assertIn("KeepMe", (target / "Harness/config/project.json").read_text(encoding="utf-8"))
        stage = self.root / "review"
        staged = stage_review_files(template, stage, plan)
        self.assertIn("HARNESS.md", staged)
        self.assertIn("Harness/scripts/tools/standard.py", staged)
        staged_harness = stage / "HARNESS.md"
        staged_harness.write_text("manual review edits\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            stage_review_files(template, stage, plan)
        stage_review_files(template, stage, plan, overwrite=True)
        self.assertEqual("new HARNESS.md\n", staged_harness.read_text(encoding="utf-8"))
    def test_update_plan_rejects_invalid_template_root(self) -> None:
        missing_template = self.root / "missing-template"
        with self.assertRaises(ValueError):
            build_update_plan(missing_template, self.root)
    def test_update_plan_stages_scaffolding_and_emits_post_apply_notes(self) -> None:
        template = self.root / "new-template"
        target = self.root / "old-project"
        for base in [template, target]:
            (base / "Harness/scripts/tools").mkdir(parents=True)
            (base / "Harness/work/archive").mkdir(parents=True)
        (template / "HARNESS.md").write_text("new rules\n", encoding="utf-8")
        (template / "Harness/work/archive/README.md").write_text("new archive guide with --before\n", encoding="utf-8")
        (template / "Harness/work/state.md").write_text("# State template\n", encoding="utf-8")
        (template / "Harness/data").mkdir()
        (template / "Harness/data/README.md").write_text("memory layer\n", encoding="utf-8")
        (template / "Harness/scripts/tools/harness_memory.py").write_text("NEW_TOOL = 1\n", encoding="utf-8")
        (template / "Harness/scripts/tools/tool_manifest.json").write_text('{"tools": [{"name": "harness_memory"}]}\n', encoding="utf-8")
        (target / "HARNESS.md").write_text("old rules\n", encoding="utf-8")
        (target / "Harness/work/archive/README.md").write_text("old archive guide, task mode only\n", encoding="utf-8")
        (target / "Harness/work/state.md").write_text("# Project state, must be preserved\n", encoding="utf-8")
        (target / "Harness/scripts/tools/tool_manifest.json").write_text('{"tools": [{"name": "project_custom_tool"}]}\n', encoding="utf-8")
        plan = build_update_plan(template, target)
        actions = {item["path"]: item["action"] for item in plan["actions"]}
        self.assertEqual("merge_review", actions["Harness/work/archive/README.md"])
        self.assertEqual("preserve", actions["Harness/work/state.md"])
        self.assertEqual("add", actions["Harness/data/README.md"])
        self.assertEqual("add", actions["Harness/scripts/tools/harness_memory.py"])
        self.assertEqual(["project_custom_tool"], plan["custom_manifest_entries"])
        notes = " ".join(plan["post_apply_notes"])
        self.assertIn("tool_manifest.json", notes)
        self.assertIn("Harness/data", notes)
        self.assertIn("project_custom_tool", notes)
        self.assertTrue(any("Harness/data/" in step for step in plan["recommended_sequence"]))
        copied = apply_missing_files(template, target, plan)
        self.assertIn("Harness/data/README.md", copied)
        self.assertIn("old archive guide, task mode only\n", (target / "Harness/work/archive/README.md").read_text(encoding="utf-8"))
        self.assertIn("must be preserved", (target / "Harness/work/state.md").read_text(encoding="utf-8"))
    def test_update_review_stage_preflights_without_partial_copy(self) -> None:
        template = self.root / "template"
        target = self.root / "target"
        stage = self.root / "review"
        template.mkdir()
        (target / "Harness").mkdir(parents=True)
        (template / "one.txt").write_text("one\n", encoding="utf-8")
        plan = {"actions": [
            {"path": "one.txt", "action": "merge_review"},
            {"path": "missing.txt", "action": "replace_review"},
        ]}
        with self.assertRaises(FileNotFoundError):
            stage_review_files(template, stage, plan, target=target)
        self.assertFalse((stage / "one.txt").exists())
    def test_update_review_stage_rejects_template_or_target_subtrees(self) -> None:
        template = self.root / "template"
        target = self.root / "target"
        (template / "Harness").mkdir(parents=True)
        (target / "Harness").mkdir(parents=True)
        (template / "HARNESS.md").write_text("new\n", encoding="utf-8")
        plan = {"actions": [{"path": "HARNESS.md", "action": "merge_review"}]}
        with self.assertRaises(ValueError):
            stage_review_files(template, template / "review", plan, target=target)
        with self.assertRaises(ValueError):
            stage_review_files(template, target / "review", plan, target=target)
    def test_update_review_stage_rolls_back_overwrite_failure(self) -> None:
        template = self.root / "template"
        target = self.root / "target"
        stage = self.root / "review"
        template.mkdir()
        (target / "Harness").mkdir(parents=True)
        stage.mkdir()
        for name in ["one.txt", "two.txt"]:
            (template / name).write_text(f"new {name}\n", encoding="utf-8")
            (stage / name).write_text(f"old {name}\n", encoding="utf-8")
        plan = {"actions": [
            {"path": "one.txt", "action": "merge_review"},
            {"path": "two.txt", "action": "replace_review"},
        ]}
        from harness_update_plan import shutil as update_shutil
        real_copy2 = update_shutil.copy2

        def fail_second_promotion(source: Path, destination: Path):
            if Path(destination) == stage / "two.txt":
                raise OSError("simulated promotion failure")
            return real_copy2(source, destination)

        with patch("harness_update_plan.shutil.copy2", side_effect=fail_second_promotion):
            with self.assertRaises(OSError):
                stage_review_files(template, stage, plan, overwrite=True, target=target)
        self.assertEqual("old one.txt\n", (stage / "one.txt").read_text(encoding="utf-8"))
        self.assertEqual("old two.txt\n", (stage / "two.txt").read_text(encoding="utf-8"))
