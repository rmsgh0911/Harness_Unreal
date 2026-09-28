"""Regression tests split from the original test_structure_tools.py."""

import hashlib

from _harness_test_base import *  # noqa: F401,F403


class UpdatePlanTests(HarnessBaseTestCase):
    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _write_contract(self, template: Path, release_files: list[str]) -> None:
        manifest = template / "Harness/template/manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 2,
            "ownership_schema_version": 1,
            "template_version": "test-v2",
            "source": {"repository": "example.invalid/template", "commit": "abc123"},
            "ownership_rules": [
                {"owner": "managed_merge", "patterns": ["HARNESS.md"]},
                {"owner": "project_owned", "patterns": ["Harness/config/project.json"]},
                {"owner": "template_owned", "patterns": ["**"]},
            ],
            "release_files": sorted(set(release_files) | {"Harness/template/manifest.json"}),
            "template_file_hashes": {},
        }
        manifest.write_text(json.dumps(payload), encoding="utf-8")

    def test_update_plan_reports_newline_only_without_normalizing_raw_hashes(self) -> None:
        template = self.root / "newline-template"
        target = self.root / "newline-target"
        for base in [template, target]:
            (base / "Harness/scripts/tools").mkdir(parents=True)
            (base / "HARNESS.md").write_text("same\n", encoding="utf-8")
        source = template / "Harness/scripts/tools/line.py"
        destination = target / "Harness/scripts/tools/line.py"
        source.write_bytes(b"ONE = 1\nTWO = 2\n")
        destination.write_bytes(b"ONE = 1\r\nTWO = 2\r\n")
        (template / "Harness/scripts/tools/blob.bin").write_bytes(b"a\r\nb")
        (target / "Harness/scripts/tools/blob.bin").write_bytes(b"a\nb")

        plan = build_update_plan(template, target)
        actions = {item["path"]: item for item in plan["actions"]}

        self.assertEqual("newline_only", actions["Harness/scripts/tools/line.py"]["difference"])
        self.assertNotEqual(actions["Harness/scripts/tools/line.py"]["local_hash"], actions["Harness/scripts/tools/line.py"]["new_hash"])
        self.assertEqual("content", actions["Harness/scripts/tools/blob.bin"]["difference"])

    def test_receipt_enables_three_way_update_classification(self) -> None:
        template = self.root / "receipt-template"
        target = self.root / "receipt-target"
        paths = {
            "Harness/scripts/tools/upstream.py": ("new upstream\n", "old\n", "old\n"),
            "Harness/scripts/tools/local.py": ("old\n", "local edit\n", "old\n"),
            "Harness/scripts/tools/both.py": ("new upstream\n", "local edit\n", "old\n"),
        }
        for base in [template, target]:
            (base / "Harness/scripts/tools").mkdir(parents=True)
            (base / "Harness/config").mkdir(parents=True)
            (base / "HARNESS.md").write_bytes(b"same\n")
        for relative, (upstream, local, _) in paths.items():
            (template / relative).write_bytes(upstream.encode("utf-8"))
            (target / relative).write_bytes(local.encode("utf-8"))
        self._write_contract(template, ["HARNESS.md", *paths])
        receipt = {
            "schema_version": 1,
            "template_version": "old",
            "files": {
                relative: {"owner": "template_owned", "baseline_sha256": self._sha(base)}
                for relative, (_, _, base) in paths.items()
            },
        }
        (target / "Harness/config/template_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

        plan = build_update_plan(template, target)
        actions = {item["path"]: item for item in plan["actions"]}

        self.assertEqual("valid", plan["receipt"]["status"])
        self.assertEqual("safe_replace", actions["Harness/scripts/tools/upstream.py"]["action"])
        self.assertEqual("keep_local", actions["Harness/scripts/tools/local.py"]["action"])
        self.assertEqual("merge_review", actions["Harness/scripts/tools/both.py"]["action"])
        self.assertEqual("known", actions["Harness/scripts/tools/both.py"]["baseline_status"])

    def test_malformed_receipt_falls_back_to_conservative_review(self) -> None:
        template = self.root / "bad-receipt-template"
        target = self.root / "bad-receipt-target"
        for base in [template, target]:
            (base / "Harness/scripts/tools").mkdir(parents=True)
            (base / "Harness/config").mkdir(parents=True)
            (base / "HARNESS.md").write_text("same\n", encoding="utf-8")
        (template / "Harness/scripts/tools/standard.py").write_text("new\n", encoding="utf-8")
        (target / "Harness/scripts/tools/standard.py").write_text("local\n", encoding="utf-8")
        (target / "Harness/config/template_receipt.json").write_text("{not json", encoding="utf-8")

        plan = build_update_plan(template, target)
        action = next(item for item in plan["actions"] if item["path"].endswith("standard.py"))

        self.assertEqual("invalid", plan["receipt"]["status"])
        self.assertEqual("replace_review", action["action"])
        self.assertEqual("unknown", action["baseline_status"])

    def test_receipt_acceptance_requires_resolved_plan_and_successful_verification(self) -> None:
        template = self.root / "accept-template"
        target = self.root / "accept-target"
        for base in [template, target]:
            (base / "Harness/scripts/tools").mkdir(parents=True)
            (base / "Harness/config").mkdir(parents=True)
            (base / "HARNESS.md").write_text("same\n", encoding="utf-8")
            (base / "Harness/scripts/tools/core.py").write_text("same\n", encoding="utf-8")
        self._write_contract(template, ["HARNESS.md", "Harness/scripts/tools/core.py"])
        (target / "Harness/template").mkdir(parents=True)
        (target / "Harness/template/manifest.json").write_bytes((template / "Harness/template/manifest.json").read_bytes())
        plan = build_update_plan(template, target)

        with self.assertRaises(RuntimeError):
            accept_receipt(template, target, plan, verifier=lambda _: False)
        self.assertFalse((target / "Harness/config/template_receipt.json").exists())

        written = accept_receipt(template, target, plan, verifier=lambda _: True)
        receipt = json.loads((target / written).read_text(encoding="utf-8"))
        self.assertEqual(1, receipt["schema_version"])
        self.assertIn("Harness/scripts/tools/core.py", receipt["files"])
        self.assertNotIn("Harness/config/project.json", receipt["files"])

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

    def test_update_plan_and_writes_reject_nested_template_target_roots(self) -> None:
        template = self.root / "template"
        nested_target = template / "nested-target"
        (template / "Harness").mkdir(parents=True)
        (template / "HARNESS.md").write_text("template\n", encoding="utf-8")
        (nested_target / "Harness").mkdir(parents=True)
        plan = {"actions": []}

        with self.assertRaisesRegex(ValueError, "non-nested"):
            build_update_plan(template, nested_target)
        with self.assertRaisesRegex(ValueError, "non-nested"):
            apply_missing_files(template, nested_target, plan)
        with self.assertRaisesRegex(ValueError, "non-nested"):
            accept_receipt(template, nested_target, plan, verifier=lambda _: True)
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
