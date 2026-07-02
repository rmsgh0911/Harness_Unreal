"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class IndexCheckTests(HarnessBaseTestCase):
    def test_index_check_warns_for_declared_missing_path(self) -> None:
        path = self.root / "Harness/index/project_index.md"
        path.write_text("# Project Index\n\n## Dashboard\n- Path: `Source/Missing.cpp`\n", encoding="utf-8")
        warnings = build_index_report(self.root)["warnings"]
        self.assertTrue(any(item["message"].startswith("declared_path_missing:Source/Missing.cpp") and item.get("line") == 4 for item in warnings))
