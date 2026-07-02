"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class DocsCheckTests(HarnessBaseTestCase):
    def test_docs_check_does_not_match_format_inside_information(self) -> None:
        from harness_docs_check import evaluate_request
        docs_config = {"request_hints": {"read": ["design"], "skip": ["format"]}, "entry_points": ["Harness/docs/README.md"]}
        result = evaluate_request("information architecture design", docs_config)
        self.assertTrue(result["should_read_docs"])
        self.assertEqual([], result["skip_hits"])

    def test_docs_check_routes_install_and_no_ci_requests_to_docs(self) -> None:
        from harness_docs_check import evaluate_request
        result = evaluate_request("install template into no CI Gitea project", {})
        self.assertTrue(result["should_read_docs"])
        self.assertIn("install", result["read_hits"])
        self.assertIn("Gitea", result["read_hits"])

        result = evaluate_request("connect Harness to this project", {})
        self.assertTrue(result["should_read_docs"])
        self.assertIn("connect", result["read_hits"])
    def test_docs_check_fallbacks_match_template_docs_json(self) -> None:
        import json
        docs_json = TOOLS_DIR.parents[1] / "config" / "docs.json"
        if not docs_json.exists():
            self.skipTest("template docs.json not found")
        with open(docs_json, encoding="utf-8") as fh:
            config = json.load(fh)
        hints = config.get("request_hints", {})
        self.assertEqual(
            sorted(REQUEST_READ_HINTS),
            sorted(hints.get("read", [])),
            "REQUEST_READ_HINTS in harness_docs_check.py does not match docs.json request_hints.read",
        )
        self.assertEqual(
            sorted(REQUEST_SKIP_HINTS),
            sorted(hints.get("skip", [])),
            "REQUEST_SKIP_HINTS in harness_docs_check.py does not match docs.json request_hints.skip",
        )
    def test_docs_check_skip_hints_take_priority_over_read_hints(self) -> None:
        from harness_docs_check import evaluate_request
        docs_config = {"request_hints": {"read": ["level"], "skip": ["compile error"]}}
        result = evaluate_request("fix level compile error", docs_config)
        self.assertFalse(result["should_read_docs"])
        self.assertTrue(result["read_hits"])
        self.assertTrue(result["skip_hits"])
    def test_docs_check_warns_about_heavy_harness_doc_root(self) -> None:
        from harness_docs_check import build_report as build_docs_report
        (self.root / "Harness/config/docs.json").write_text(
            '{"doc_roots": ["Harness/docs"], "entry_points": ["Harness/docs/README.md"], '
            '"read_policy": {"default": "on_demand", "read_when": ["spec"], "do_not_read_when": ["format"]}}\n',
            encoding="utf-8",
        )
        docs = self.root / "Harness/docs"
        docs.mkdir()
        (docs / "README.md").write_text("# Document Map\n", encoding="utf-8")
        report = build_docs_report(self.root)
        self.assertFalse(any("heavy" in item["message"] for item in report["findings"]))
        exports = docs / "figma_exports"
        exports.mkdir()
        for index in range(201):
            (exports / f"icon_{index}.png").write_bytes(b"\x89PNG fake image data")
        report = build_docs_report(self.root)
        heavy = [item for item in report["findings"] if "heavy" in item["message"]]
        self.assertEqual(1, len(heavy))
        self.assertEqual("warning", heavy[0]["level"])
        self.assertIn("binary files", heavy[0]["message"])
    def test_docs_index_lists_headings_from_configured_roots(self) -> None:
        (self.root / "Harness/config/docs.json").write_text(json.dumps({"doc_roots": ["Harness/docs"]}), encoding="utf-8")
        docs = self.root / "Harness/docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "Guide.md").write_text("# Guide Title\n\n## Section A\n\ntext\n\n## Section B\n", encoding="utf-8")
        index = build_docs_index(self.root)
        self.assertEqual(1, index["file_count"])
        entry = index["files"][0]
        self.assertEqual("Guide Title", entry["title"])
        self.assertEqual(["Guide Title", "Section A", "Section B"], [h["title"] for h in entry["headings"]])
