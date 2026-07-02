"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class ProgressTests(HarnessBaseTestCase):
    def test_context_includes_task_iteration_progress(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        context = build_context(self.root, request="3 cycles", task="repeat")
        status = context["cycle_policy"]["iteration_status"]
        self.assertEqual(1, status["completed_cycles"])
        self.assertEqual(2, status["remaining_cycles"])
    def test_handoff_uses_filtered_next_and_iteration_progress(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        handoff = build_handoff(self.root, request="3 cycles dashboard input", task="repeat")
        self.assertIn("## Iteration", handoff)
        self.assertIn("- Progress: 1/3", handoff)
        self.assertIn("- Repair dashboard input routing.", handoff)
        self.assertNotIn("- Verify terrain export bounds.", handoff)
    def test_progress_html_serve_targets_localhost_and_harness_dir(self) -> None:
        httpd, url = build_progress_server(self.root, port=0)
        try:
            self.assertTrue(url.startswith("http://127.0.0.1:"))
            self.assertTrue(url.endswith("/Progress_index.html"))
            self.assertEqual(str(self.root / "Harness"), httpd.RequestHandlerClass.keywords["directory"])
        finally:
            httpd.server_close()
    def test_progress_html_writes_tracked_dashboard(self) -> None:
        report = build_progress_html_report(self.root, write=True)
        output = self.root / "Harness/Progress_index.html"
        self.assertTrue(report["ok"])
        self.assertTrue(report["output_exists"])
        self.assertEqual("dynamic-source", report["viewer_mode"])
        self.assertTrue(output.exists())
        html = output.read_text(encoding="utf-8")
        self.assertIn("<title>Harness Progress</title>", html)
        self.assertIn('name="harness-progress-viewer" content="dynamic-source"', html)
        self.assertIn('name="harness-progress-source" content="Harness/Progress.md"', html)
        self.assertIn('const SOURCE = "Progress.md";', html)
        self.assertIn('id="file-hint"', html)
        self.assertIn("Progress_view.cmd", html)
        self.assertIn("harness_progress_html.py --serve", html)
        self.assertNotIn("?묒꽦 ?꾩슂:", html)
    def test_progress_parses_last_updated_and_warns_when_missing(self) -> None:
        report = build_progress_report(self.root)
        self.assertEqual("2026-07-02 14:30:45", report["last_updated"])
        self.assertNotIn("missing_last_updated_header", report["warnings"])
        without_header = VALID_PROGRESS.replace("**Last updated:** 2026-07-02 14:30:45 +09:00\n\n", "")
        (self.root / "Harness/Progress.md").write_text(without_header, encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertIsNone(report["last_updated"])
        self.assertIn("missing_last_updated_header", report["warnings"])
        self.assertTrue(report["ok"])  # header is a merge aid, not a hard gate
    def test_progress_rejects_date_log(self) -> None:
        path = self.root / "Harness/Progress.md"
        path.write_text(VALID_PROGRESS + "\n2026-01-01 done\n2026-01-02 done\n2026-01-03 done\n2026-01-04 done\n", encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertFalse(report["ok"])
        self.assertIn("appears_to_be_date_log:4", report["errors"])
    def test_progress_rejects_fifth_section(self) -> None:
        path = self.root / "Harness/Progress.md"
        path.write_text(VALID_PROGRESS + "\n## 기록\n\n- 오래된 기록\n", encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item.startswith("unexpected_sections:") for item in report["errors"]))
    def test_progress_rejects_more_than_40_lines(self) -> None:
        path = self.root / "Harness/Progress.md"
        path.write_text(VALID_PROGRESS + "\n".join("<!-- padding -->" for _ in range(30)), encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertFalse(report["ok"])
        self.assertIn("longer_than_hard_limit:40", report["errors"])
    def test_progress_rejects_too_many_section_bullets(self) -> None:
        path = self.root / "Harness/Progress.md"
        path.write_text(VALID_PROGRESS.replace("- 기능 A가 동작합니다.", "- A\n- B\n- C\n- D"), encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item.startswith("section_bullets_exceed_limit:") for item in report["errors"]))
    def test_progress_view_launcher_is_tracked_and_invokes_serve(self) -> None:
        launcher = TOOLS_DIR.parents[2] / "Harness/Progress_view.cmd"
        self.assertTrue(launcher.exists())
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("harness_progress_html.py", text)
        self.assertIn("--serve", text)
    def test_valid_progress_passes(self) -> None:
        self.assertTrue(build_progress_report(self.root)["ok"])
