from __future__ import annotations

from _harness_test_base import *  # noqa: F401,F403


class ProjectReadinessTests(HarnessBaseTestCase):
    def test_project_readiness_allows_standalone_template(self) -> None:
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({"template_mode": True, "project_name": "", "uproject_file": "", "build": {}}),
            encoding="utf-8",
        )
        report = build_project_readiness_report(self.root)
        self.assertTrue(report["ok"])
        self.assertEqual("template_mode", report["status"])

    def test_project_readiness_fails_when_template_mode_remains_in_project(self) -> None:
        (self.root / "Demo.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({"template_mode": True, "project_name": "", "uproject_file": "", "build": {}}),
            encoding="utf-8",
        )
        report = build_project_readiness_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("template_mode is still true" in item["message"] for item in report["findings"]))

    def test_project_readiness_requires_real_project_connection_files(self) -> None:
        (self.root / "Demo.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({
                "template_mode": False,
                "project_name": "Demo",
                "uproject_file": "Demo.uproject",
                "engine_version": "5.6",
                "build": {"engine_root": "C:/UE_5.6", "editor_target_name": "DemoEditor", "game_target_name": "Demo"},
            }),
            encoding="utf-8",
        )
        # A lingering placeholder is a soft freshness warning: it does not block
        # standard verify_all, but --strict promotes it to blocking.
        (self.root / "Harness/work/state.md").write_text("# State\n\n## Project\n- TODO\n", encoding="utf-8")
        report = build_project_readiness_report(self.root)
        self.assertTrue(report["ok"])
        self.assertTrue(any(item["path"] == "Harness/work/state.md" and item["level"] == "warning" for item in report["findings"]))
        strict = build_project_readiness_report(self.root, strict=True)
        self.assertFalse(strict["ok"])

        (self.root / "Harness/work/state.md").write_text("# State\n\n## Project\n- Demo\n", encoding="utf-8")
        (self.root / "Harness/work/next.md").write_text("# Next\n\n## Active Work\n- Confirm first feature.\n", encoding="utf-8")
        (self.root / "Harness/index/project_index.md").write_text("# Project Index\n\n## Main\n- Path: `Source/UI/Dashboard.cpp`\n", encoding="utf-8")
        report = build_project_readiness_report(self.root)
        self.assertTrue(report["ok"])
        self.assertTrue(build_project_readiness_report(self.root, strict=True)["ok"])

    def test_project_readiness_hard_error_blocks_even_in_standard_mode(self) -> None:
        (self.root / "Demo.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({
                "template_mode": False,
                "project_name": "Demo",
                "uproject_file": "Demo.uproject",
                "engine_version": "5.6",
                "build": {"engine_root": "", "editor_target_name": "DemoEditor", "game_target_name": "Demo"},
            }),
            encoding="utf-8",
        )
        (self.root / "Harness/work/state.md").write_text("# State\n\n## Project\n- Demo\n", encoding="utf-8")
        (self.root / "Harness/work/next.md").write_text("# Next\n\n## Active Work\n- Confirm first feature.\n", encoding="utf-8")
        (self.root / "Harness/index/project_index.md").write_text("# Project Index\n\n## Main\n- Path: `Source/UI/Dashboard.cpp`\n", encoding="utf-8")
        report = build_project_readiness_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("build.engine_root" in item["message"] and item["level"] == "error" for item in report["findings"]))

    def _connect_project(self) -> None:
        (self.root / "Demo.uproject").write_text("{}", encoding="utf-8")
        (self.root / "Harness/config/project.json").write_text(
            json.dumps({
                "template_mode": False,
                "project_name": "Demo",
                "uproject_file": "Demo.uproject",
                "engine_version": "5.6",
                "build": {"engine_root": "C:/UE_5.6", "editor_target_name": "DemoEditor", "game_target_name": "Demo"},
            }),
            encoding="utf-8",
        )
        (self.root / "Harness/work/state.md").write_text("# State\n\n## Project\n- Demo\n", encoding="utf-8")
        (self.root / "Harness/index/project_index.md").write_text("# Project Index\n\n## Main\n- Path: `Source/UI/Dashboard.cpp`\n", encoding="utf-8")

    def test_project_readiness_allows_real_notes_that_mention_todo(self) -> None:
        self._connect_project()
        (self.root / "Harness/work/next.md").write_text(
            "# Next\n\n## Active Work\n- Fix the TODO left in Source/Demo/Character.cpp for jump buffering.\n",
            encoding="utf-8",
        )
        report = build_project_readiness_report(self.root)
        self.assertTrue(report["ok"], report["findings"])

    def test_project_readiness_reports_malformed_uproject_without_crashing(self) -> None:
        self._connect_project()
        (self.root / "Harness/work/next.md").write_text("# Next\n\n## Active Work\n- Confirm first feature.\n", encoding="utf-8")
        (self.root / "Demo.uproject").write_text("not valid json", encoding="utf-8")
        report = build_project_readiness_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("valid JSON" in item["message"] and item["path"] == "Demo.uproject" for item in report["findings"]))
