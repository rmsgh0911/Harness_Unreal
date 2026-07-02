"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class ToolUsageTests(HarnessBaseTestCase):
    def test_tool_usage_flags_low_reference_and_counts_wiring(self) -> None:
        from harness_tool_usage import build_report as build_tool_usage
        tools = self.root / "Harness/scripts/tools"
        (tools / "harness_verify_all.py").write_text("import harness_wired\n", encoding="utf-8")
        (tools / "harness_context.py").write_text("# orchestrator\n", encoding="utf-8")
        (tools / "harness_wired.py").write_text("WIRED = 1\n", encoding="utf-8")
        (tools / "harness_orphan.py").write_text("ORPHAN = 1\n", encoding="utf-8")
        (tools / "harness_common.py").write_text("SHARED = 1\n", encoding="utf-8")
        (tools / "tool_manifest.json").write_text('{"tools": [{"name": "harness_wired"}]}\n', encoding="utf-8")
        (self.root / "HARNESS.md").write_text("# Harness\nUse harness_wired for work.\n", encoding="utf-8")
        report = build_tool_usage(self.root)
        by_name = {tool["name"]: tool for tool in report["tools"]}
        self.assertNotIn("harness_common", by_name)  # shared library, not a tool
        self.assertTrue(by_name["harness_wired"]["wired_into_orchestrator"])
        self.assertGreaterEqual(by_name["harness_wired"]["doc_reference_count"], 1)
        self.assertFalse(by_name["harness_wired"]["low_reference"])
        self.assertTrue(by_name["harness_orphan"]["low_reference"])
        self.assertIn("harness_orphan", report["low_reference"])
        self.assertIn("harness_orphan", report["unregistered"])
