"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class ScanProjectTests(HarnessBaseTestCase):
    def test_diff_guard_standard_prefixes_do_not_contain_project_paths(self) -> None:
        known_standard = {"Source/", "Config/", "Content/", "Plugins/", "Harness/scripts/unreal/"}
        unexpected = [p for p in PROGRESS_TRIGGER_PREFIXES if p not in known_standard]
        self.assertEqual([], unexpected, f"non-standard prefixes in PROGRESS_TRIGGER_PREFIXES: {unexpected}")
    def test_project_fill_deep_fill_respects_overwrite(self) -> None:
        existing = {"a": "keep", "build": {"x": "keep"}}
        candidate = {"a": "new", "b": "add", "build": {"x": "new", "y": "add"}}
        self.assertEqual(
            {"a": "keep", "b": "add", "build": {"x": "keep", "y": "add"}},
            deep_fill(existing, candidate, overwrite=False),
        )
        self.assertEqual(
            {"a": "new", "b": "add", "build": {"x": "new", "y": "add"}},
            deep_fill(existing, candidate, overwrite=True),
        )
    def test_project_fill_gates_write_and_preserves_existing_values(self) -> None:
        (self.root / "Demo.uproject").write_text(
            json.dumps({"EngineAssociation": "5.4", "Modules": [{"Name": "Demo"}]}),
            encoding="utf-8",
        )
        (self.root / "Source/DemoEditor.Target.cs").write_text("// editor\n", encoding="utf-8")
        project_json = self.root / "Harness/config/project.json"
        project_json.write_text(json.dumps({"project_name": "Keep", "template_mode": True}), encoding="utf-8")

        dry = build_project_fill_report(self.root, write=False)
        self.assertEqual("dry_run", dry["status"])
        self.assertTrue(dry["changed"])
        self.assertEqual("Keep", json.loads(project_json.read_text(encoding="utf-8"))["project_name"])

        written = build_project_fill_report(self.root, write=True)
        self.assertEqual("written", written["status"])
        merged = json.loads(project_json.read_text(encoding="utf-8"))
        self.assertEqual("Keep", merged["project_name"])
        self.assertTrue(merged["template_mode"])
        self.assertEqual("Demo.uproject", merged["uproject_file"])
        self.assertEqual("DemoEditor", merged["build"]["editor_target_name"])

        self.assertEqual("unchanged", build_project_fill_report(self.root, write=True)["status"])
    def test_scan_builds_project_json_candidate_from_structure(self) -> None:
        (self.root / "Demo.uproject").write_text(
            json.dumps({"EngineAssociation": "5.4", "Modules": [{"Name": "Demo"}]}),
            encoding="utf-8",
        )
        source = self.root / "Source/Demo"
        source.mkdir(parents=True, exist_ok=True)
        (source / "Demo.Build.cs").write_text("// build\n", encoding="utf-8")
        (self.root / "Source/Demo.Target.cs").write_text("// game\n", encoding="utf-8")
        (self.root / "Source/DemoEditor.Target.cs").write_text("// editor\n", encoding="utf-8")
        report = scan(self.root)
        self.assertIn("Demo", report["source"]["modules"])
        self.assertEqual(["DemoEditor"], report["source"]["editor_targets"])
        self.assertEqual(["Demo"], report["source"]["game_targets"])
        candidate = report["project_json_candidate"]
        self.assertEqual("Demo", candidate["project_name"])
        self.assertEqual("Demo.uproject", candidate["uproject_file"])
        self.assertEqual("5.4", candidate["engine_version"])
        self.assertEqual("DemoEditor", candidate["build"]["editor_target_name"])
        self.assertEqual("Demo", candidate["build"]["game_target_name"])
    def test_scan_leaves_candidate_blank_when_uproject_is_ambiguous(self) -> None:
        (self.root / "One.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Two.uproject").write_text("{}", encoding="utf-8")
        candidate = scan(self.root)["project_json_candidate"]
        self.assertEqual("", candidate["project_name"])
        self.assertEqual("", candidate["uproject_file"])

    def test_scan_marks_malformed_uproject_unreadable_without_crashing(self) -> None:
        (self.root / "Broken.uproject").write_text("not json {", encoding="utf-8")
        report = scan(self.root)
        self.assertEqual(1, len(report["uprojects"]))
        self.assertFalse(report["uprojects"][0]["readable"])
        self.assertEqual([], report["uprojects"][0]["modules"])
    def test_init_plan_includes_project_readiness_gate(self) -> None:
        from harness_init_plan import build_plan
        plan = build_plan(self.root)
        self.assertIn("python Harness/scripts/tools/harness_project_readiness.py", plan["verify"])
    def test_task_template_uses_provider_neutral_branch_placeholder(self) -> None:
        root = TOOLS_DIR.parents[2]
        task_example = (root / "Harness/work/tasks/task.example.md").read_text(encoding="utf-8")
        self.assertIn("- Branch: <agent>/example-task", task_example)
        self.assertNotIn("- Branch: codex/", task_example)
