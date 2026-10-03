"""Cross-tool workflow contracts beyond the optional database layer."""
from _harness_test_base import *  # noqa: F401,F403
from harness_common import config_preflight
from harness_verify_all import build_verify_all
import harness_unreal_script as unreal_script


class ConfigurationContractTests(HarnessBaseTestCase):
    def test_worker_instruction_types_and_paths_fail_preflight_not_traceback(self):
        path = self.root / "Harness/config/agents.json"
        for value in ([], {}, None, True, "", "../outside.md", "C:/outside.md", "/outside.md"):
            with self.subTest(value=value):
                path.write_text(json.dumps({"supported_workers": {"fixture": {"instruction_file": value}}}), encoding="utf-8")
                self.assertFalse(config_preflight(self.root)["ok"])
                self.assertFalse(run_doctor(self.root)["ok"])
                self.assertTrue(build_verify_all(self.root)["preflight_failed"])

    def test_invalid_config_is_reported_before_nested_tool_execution(self):
        path = self.root / "Harness/config/project.json"
        for value in ('{invalid', '[]', '{"template_mode":"false"}', '{"build":[]}', '{"build":{"engine_root":true}}'):
            with self.subTest(value=value):
                path.write_text(value, encoding="utf-8")
                self.assertFalse(config_preflight(self.root)["ok"])
                self.assertFalse(run_doctor(self.root)["ok"])
                self.assertFalse(build_project_readiness_report(self.root)["ok"])
                with patch("harness_verify_all.run_tool_tests") as tests:
                    report = build_verify_all(self.root)
                self.assertFalse(report["ok"])
                self.assertTrue(report["preflight_failed"])
                tests.assert_not_called()
                with self.assertRaises(ValueError):
                    build_context(self.root)

    def test_core_collection_shapes_are_not_silently_coerced(self):
        for relative, value in (("config/docs.json", '{"doc_roots":"Harness/docs"}'),
                                ("config/cycle_policy.json", '{"default_max_cycles":true}'),
                                ("scripts/tools/tool_manifest.json", '{"tools":[{"path":[]}]}')):
            with self.subTest(relative=relative):
                path = self.root / "Harness" / relative
                before = path.read_bytes() if path.exists() else None
                path.write_text(value, encoding="utf-8")
                self.assertFalse(config_preflight(self.root)["ok"])
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)


class ExecutionContractTests(HarnessBaseTestCase):
    def ready_report(self):
        engine = self.root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        engine.parent.mkdir(parents=True)
        engine.write_bytes(b"fixture only; never executed")
        script = self.root / "Harness/scripts/unreal/test.py"
        script.parent.mkdir(parents=True)
        script.write_text("import unreal", encoding="utf-8")
        (self.root / "Demo.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Harness/config/project.json").write_text(json.dumps({"uproject_file": "Demo.uproject", "build": {"engine_root": str(self.root)}}), encoding="utf-8")
        return unreal_script.build_report(self.root, "Harness/scripts/unreal/test.py")

    def test_failed_process_never_reports_success_or_acceptance(self):
        report = self.ready_report()
        self.assertEqual("not_run", report["execution"])
        from subprocess import CompletedProcess
        with patch("harness_unreal_script.subprocess.run", return_value=CompletedProcess([], 7)) as run:
            result = unreal_script.run_report(self.root, report, json_output=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["ready"])
        self.assertTrue(result["ran"])
        self.assertEqual("process_failed", result["execution"])
        self.assertEqual("not_evaluated", result["acceptance"])
        self.assertIs(sys.stderr, run.call_args.kwargs["stdout"])
        self.assertIn("Exit code: 7", unreal_script.format_text(result))

    def test_missing_executable_and_reserved_arguments_fail_closed(self):
        report = self.ready_report()
        with patch("harness_unreal_script.subprocess.run", side_effect=OSError("missing executable")):
            result = unreal_script.run_report(self.root, report)
        self.assertFalse(result["ran"])
        self.assertEqual("launch_failed", result["execution"])
        blocked = unreal_script.build_report(self.root, "Harness/scripts/unreal/test.py", ["-script=other.py"])
        with patch("harness_unreal_script.subprocess.run") as run:
            self.assertEqual("blocked", unreal_script.run_report(self.root, blocked)["execution"])
        run.assert_not_called()

    def test_directory_is_not_an_executable_or_script(self):
        report = self.ready_report()
        script = self.root / "Harness/scripts/unreal/test.py"
        script.unlink()
        script.mkdir()
        self.assertFalse(unreal_script.build_report(self.root, str(script))["ready"])

    def test_relative_engine_root_is_resolved_from_project_not_caller(self):
        self.ready_report()
        config = self.root / "Harness/config/project.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["build"]["engine_root"] = "."
        config.write_text(json.dumps(value), encoding="utf-8")
        report = unreal_script.build_report(self.root, "Harness/scripts/unreal/test.py")
        self.assertTrue(report["ready"], report)
        self.assertEqual(self.root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe", Path(report["command"][0]))


class HandoffContractTests(HarnessBaseTestCase):
    def test_unknown_git_does_not_look_like_a_clean_tree(self):
        import harness_handoff as handoff
        with patch("harness_diff_guard.run_git_status", return_value=(False, [])):
            text = handoff.build_handoff(self.root, task="missing-task")
        self.assertIn("## Evidence Warnings", text)
        self.assertIn("task record is missing", text)
        self.assertIn("unknown; ordinary staged/unstaged/untracked", text)
        self.assertNotIn("- none detected", text)

    def test_handoff_retains_change_groups_and_omission_count(self):
        import harness_handoff as handoff
        changes = ['MM "partial.md"', '?? "new.md"'] + [f'M  "file-{i}.md"' for i in range(42)]
        with patch("harness_diff_guard.run_git_status", return_value=(True, changes)):
            text = handoff.build_handoff(self.root)
        self.assertIn("### Staged: 43", text)
        self.assertIn("### Unstaged: 1", text)
        self.assertIn("### Untracked: 1", text)
        self.assertIn("Omitted paths: 3", text)

    def test_handoff_write_cannot_overwrite_source_and_is_relative_to_root(self):
        from harness_handoff import write_handoff
        source = self.root / "HARNESS.md"
        before = source.read_bytes()
        with self.assertRaises(ValueError):
            write_handoff(self.root, Path("HARNESS.md"), "# Harness Handoff\n")
        self.assertEqual(before, source.read_bytes())
        output = write_handoff(self.root, Path("Harness/handoff.md"), "# Harness Handoff\nfirst\n")
        self.assertTrue(output.is_file())
        write_handoff(self.root, output, "# Harness Handoff\nsecond\n")
        self.assertIn("second", output.read_text(encoding="utf-8"))


class PolicyContractTests(HarnessBaseTestCase):
    def test_junction_guard_supports_python_without_path_is_junction(self):
        from harness_common import is_link_or_junction
        from types import SimpleNamespace
        legacy_path = SimpleNamespace(is_symlink=lambda: False,
                                      lstat=lambda: SimpleNamespace(st_file_attributes=0x400))
        self.assertTrue(is_link_or_junction(legacy_path))
        ordinary = SimpleNamespace(is_symlink=lambda: False,
                                   lstat=lambda: SimpleNamespace(st_file_attributes=0))
        self.assertFalse(is_link_or_junction(ordinary))
        cloud_file = SimpleNamespace(is_symlink=lambda: False,
                                     lstat=lambda: SimpleNamespace(st_file_attributes=0x400, st_reparse_tag=0x9000001A))
        self.assertFalse(is_link_or_junction(cloud_file))

    def test_shipped_policy_matches_runtime_cycle_modes_and_tool_ownership(self):
        template = TOOLS_DIR.parents[2]
        policy = json.loads((template / "Harness/config/cycle_policy.json").read_text(encoding="utf-8"))
        modes = policy["cycle_count_rules"]["budget_modes"]
        for request, mode in (("8 cycles", "exact_count"), ("up to 8 cycles", "upper_bound")):
            actual = evaluate_cycle_request(request, policy)
            for key, expected in modes[mode].items():
                self.assertEqual(expected, actual[key], (mode, key))
        tools = policy["tool_policy"]
        self.assertEqual("Harness/scripts/project", tools["default_tool_directory"])
        self.assertEqual("Harness/scripts/tools", tools["standard_tool_directory"])
        self.assertTrue((template / tools["manifest"]).is_file())
        self.assertTrue((template / tools["standard_manifest"]).is_file())
        self.assertIn("build_failed_twice_for_the_same_reason", policy["stop_conditions"])
        self.assertNotIn("build_failed_twice", policy["stop_conditions"])

    def test_git_configuration_injection_is_removed_from_readonly_evidence(self):
        import os
        from harness_common import readonly_git_env
        with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor",
                                    "GIT_CONFIG_VALUE_0": "external-helper", "GIT_CONFIG_PARAMETERS": "override"}):
            environment = readonly_git_env()
        self.assertFalse(any(key.startswith(("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_CONFIG_PARAMETERS")) for key in environment))
