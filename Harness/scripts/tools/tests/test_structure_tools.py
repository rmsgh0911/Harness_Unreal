from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from harness_context import build_context  # noqa: E402
from harness_context import evaluate_cycle_request  # noqa: E402
from harness_archive import apply_archive, build_plan as build_archive_plan  # noqa: E402
from harness_cycle import build_entry, validate_iteration_entry  # noqa: E402
from harness_cycle_summary import analyze_iteration, build_summary as build_cycle_summary, parse_cycle_file  # noqa: E402
from harness_diff_guard import PROGRESS_TRIGGER_PREFIXES  # noqa: E402
from harness_docs_check import REQUEST_READ_HINTS, REQUEST_SKIP_HINTS  # noqa: E402
from harness_index_check import build_report as build_index_report  # noqa: E402
from harness_iteration_status import build_status as build_iteration_status  # noqa: E402
from harness_handoff import build_handoff  # noqa: E402
from harness_knowledge import build_knowledge  # noqa: E402
from harness_progress_check import build_report as build_progress_report  # noqa: E402
from harness_state_check import build_report as build_state_report  # noqa: E402
from harness_update_plan import apply_missing_files, build_update_plan, stage_review_files  # noqa: E402


VALID_PROGRESS = """# Progress

짧은 현재 대시보드입니다.

## 현재 상태

- 기능 A가 동작합니다.

## 최근 완료

- 기능 A 검증을 마쳤습니다.

## 확인 필요

- PIE 확인이 필요합니다.

## 다음 작업

- 기능 B를 구현합니다.
"""


class HarnessStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "Harness/work").mkdir(parents=True)
        (self.root / "Harness/index").mkdir(parents=True)
        (self.root / "Harness/config").mkdir(parents=True)
        (self.root / "Harness/scripts/tools").mkdir(parents=True)
        (self.root / "Source/UI").mkdir(parents=True)
        (self.root / "Source/UI/Dashboard.cpp").write_text("// dashboard\n", encoding="utf-8")
        (self.root / "HARNESS.md").write_text("# Harness\n", encoding="utf-8")
        (self.root / "Harness/README.md").write_text("# Harness Folder\n", encoding="utf-8")
        (self.root / "Harness/Progress.md").write_text(VALID_PROGRESS, encoding="utf-8")
        (self.root / "Harness/work/state.md").write_text(
            "# State\n\n## Project\n- Demo\n\n## Current State\n- Ready\n\n"
            "## Latest Verification\n- Unit tests\n\n## Risks\n- None\n",
            encoding="utf-8",
        )
        (self.root / "Harness/work/next.md").write_text(
            "# Next\n\n## Active Work\n- Repair dashboard input routing.\n- Verify terrain export bounds.\n",
            encoding="utf-8",
        )
        (self.root / "Harness/index/project_index.md").write_text(
            "# Project Index\n\n## Dashboard\n- Path: `Source/UI/Dashboard.cpp`\n- Verify: `python verify_dashboard.py`\n\n"
            "## Terrain\n- Path: `Source/Terrain/Exporter.cpp`\n- Verify: `python verify_terrain.py`\n",
            encoding="utf-8",
        )
        (self.root / "Harness/index/api_surface.md").write_text("# API Surface\n\n## Public Names\n- Widget hooks\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_progress_passes(self) -> None:
        self.assertTrue(build_progress_report(self.root)["ok"])

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

    def test_progress_rejects_date_log(self) -> None:
        path = self.root / "Harness/Progress.md"
        path.write_text(VALID_PROGRESS + "\n2026-01-01 done\n2026-01-02 done\n2026-01-03 done\n2026-01-04 done\n", encoding="utf-8")
        report = build_progress_report(self.root)
        self.assertFalse(report["ok"])
        self.assertIn("appears_to_be_date_log:4", report["errors"])

    def test_state_check_warns_about_completed_next_item(self) -> None:
        path = self.root / "Harness/work/next.md"
        path.write_text("# Next\n\n## Active Work\n- [x] Old work\n- New work\n", encoding="utf-8")
        findings = build_state_report(self.root)["findings"]
        self.assertTrue(any("completed checklist items" in item["message"] and item.get("line") == 4 for item in findings))

    def test_state_check_warns_about_stale_consolidation_and_long_state(self) -> None:
        lines = ["# State", "", "Last consolidated: 2000-01-01", "", "## Project", "- Demo", "", "## Current State"]
        lines.extend(f"- Confirmed fact {number}" for number in range(75))
        lines.extend(["", "## Latest Verification", "- Unit tests", "", "## Risks", "- None"])
        (self.root / "Harness/work/state.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = build_state_report(self.root)
        state_doc = next(item for item in report["docs"] if item["path"].endswith("state.md"))
        self.assertIn("longer_than_soft_limit:80", state_doc["warnings"])
        self.assertTrue(any("Last consolidated" in item["message"] and item.get("line") == 3 for item in report["findings"]))

    def test_state_check_warns_when_next_has_more_than_five_items(self) -> None:
        items = "\n".join(f"- Active item {number}" for number in range(6))
        (self.root / "Harness/work/next.md").write_text(f"# Next\n\n## Active Work\n{items}\n", encoding="utf-8")
        findings = build_state_report(self.root)["findings"]
        self.assertTrue(any("too many active project items" in item["message"] for item in findings))

    def test_state_check_reports_duplicate_and_encoding_lines(self) -> None:
        duplicate = "A sufficiently long confirmed project fact."
        (self.root / "Harness/work/state.md").write_text(
            f"# State\n\n## Project\n- {duplicate}\n\n## Current State\n- Ready\n\n"
            "## Latest Verification\n- Unit tests\n\n## Risks\n- None\n",
            encoding="utf-8",
        )
        (self.root / "Harness/work/next.md").write_text(f"# Next\n\n## Active Work\n- {duplicate}\n- Broken � text\n", encoding="utf-8")
        findings = build_state_report(self.root)["findings"]
        self.assertTrue(any("duplicate current-document bullet" in item["message"] and item.get("line") for item in findings))
        self.assertTrue(any("mojibake" in item["message"] and item.get("line") for item in findings))

    def test_context_filters_unrelated_next_items(self) -> None:
        context = build_context(self.root, request="Fix dashboard input")
        self.assertEqual(["Repair dashboard input routing."], context["next_items"])
        self.assertEqual("Dashboard", context["project_index"]["matched_sections"][0]["section"])
        route = context["project_index"]["matched_sections"][0]
        self.assertEqual(["Source/UI/Dashboard.cpp"], route["paths"])
        self.assertEqual(["python verify_dashboard.py"], route["verification"])

    def test_context_keeps_file_priority_for_multiple_matches(self) -> None:
        context = build_context(self.root, request="Verify dashboard input and terrain export bounds")
        self.assertEqual(
            ["Repair dashboard input routing.", "Verify terrain export bounds."],
            context["next_items"],
        )

    def test_context_all_next_preserves_file_order(self) -> None:
        context = build_context(self.root, request="unrelated request", all_next=True)
        self.assertEqual(
            ["Repair dashboard input routing.", "Verify terrain export bounds."],
            context["next_items"],
        )

    def test_context_keeps_explicit_api_routing_hint(self) -> None:
        context = build_context(self.root, request="API 변경")
        self.assertIn("Harness/index/api_surface.md", context["project_index"]["recommended_first_reads"])

    def test_cycle_request_distinguishes_exact_and_upper_bound_budgets(self) -> None:
        exact = evaluate_cycle_request("10 cycles", {"default_max_cycles": 1, "cycle_count_rules": {"phrases": []}})
        upper = evaluate_cycle_request("up to 10 cycles", {"default_max_cycles": 1, "cycle_count_rules": {"phrases": []}})
        self.assertEqual("exact_count", exact["budget_mode"])
        self.assertEqual(10, exact["requested_exact_count"])
        self.assertFalse(exact["max_cycles_is_upper_bound"])
        self.assertFalse(exact["stop_before_max_when_success_criteria_met"])
        self.assertEqual("upper_bound", upper["budget_mode"])
        self.assertTrue(upper["max_cycles_is_upper_bound"])
        self.assertTrue(upper["stop_before_max_when_success_criteria_met"])

    def test_cycle_record_query_does_not_trigger_iteration_mode(self) -> None:
        policy = {"default_max_cycles": 1, "cycle_count_rules": {"phrases": ["cycle", "cycles", "반복"]}}
        self.assertFalse(evaluate_cycle_request("search existing cycle log records", policy)["is_cycle_work"])
        self.assertTrue(evaluate_cycle_request("repeat validation", policy)["is_cycle_work"])

    def test_harness_update_context_routes_to_install_guide(self) -> None:
        (self.root / "INSTALL.md").write_text("# Install\n", encoding="utf-8")
        context = build_context(self.root, request="older Harness update")
        self.assertIn("INSTALL.md", context["recommended_first_reads"])
        self.assertFalse(context["cycle_policy"]["request_eval"]["is_cycle_work"])

    def test_context_includes_task_iteration_progress(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        context = build_context(self.root, request="3 cycles", task="repeat")
        status = context["cycle_policy"]["iteration_status"]
        self.assertEqual(1, status["completed_cycles"])
        self.assertEqual(2, status["remaining_cycles"])

    def test_index_check_warns_for_declared_missing_path(self) -> None:
        path = self.root / "Harness/index/project_index.md"
        path.write_text("# Project Index\n\n## Dashboard\n- Path: `Source/Missing.cpp`\n", encoding="utf-8")
        warnings = build_index_report(self.root)["warnings"]
        self.assertTrue(any(item["message"].startswith("declared_path_missing:Source/Missing.cpp") and item.get("line") == 4 for item in warnings))

    def test_archive_requires_completed_status_and_preserves_task_id(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        cycles = self.root / "Harness/work/cycles"
        tasks.mkdir()
        cycles.mkdir()
        (tasks / "done-task.md").write_text("# Task\n\n- Status: completed\n", encoding="utf-8")
        (cycles / "done-task.md").write_text("# Cycle\n", encoding="utf-8")
        plan = build_archive_plan(self.root, "done-task", "2026-06")
        self.assertTrue(plan["ready"])
        moved = apply_archive(self.root, plan)
        self.assertEqual(2, len(moved))
        index = (self.root / "Harness/work/archive/index.md").read_text(encoding="utf-8")
        self.assertIn("`done-task`", index)

    def test_cycle_entry_records_budget_decision_and_success_criteria(self) -> None:
        entry = build_entry(
            "Iteration",
            ["changed"],
            ["verified"],
            ["remaining"],
            worker="Codex",
            cycle_number=3,
            max_cycles=10,
            decision="continue",
            success_criteria=["repeatable verification"],
        )
        self.assertIn("- Cycle: 3/10", entry)
        self.assertIn("- Decision: continue", entry)
        self.assertIn("- Success Criteria: repeatable verification", entry)

    def test_cycle_summary_parses_structured_iteration_fields(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 Iteration\n\n- Worker: Codex\n- Cycle: 3/10\n- Decision: continue\n"
            "- Success Criteria: repeatable verification\n- Changed: tool\n- Verified: unit test\n- Remaining: docs\n",
            encoding="utf-8",
        )
        section = parse_cycle_file(path)["sections"][0]
        self.assertEqual(3, section["cycle_number"])
        self.assertEqual(10, section["max_cycles"])
        self.assertEqual("continue", section["decision"])
        self.assertEqual(["repeatable verification"], section["success_criteria"])

    def test_cycle_summary_reports_invalid_iteration_sequence(self) -> None:
        sections = [
            {"cycle_number": 1, "max_cycles": 5, "decision": "stop_success"},
            {"cycle_number": 3, "max_cycles": 4, "decision": "continue"},
        ]
        status = analyze_iteration(sections)
        self.assertIn("cycle numbers are not a contiguous 1-based sequence", status["warnings"])
        self.assertIn("cycle budget changed within one log", status["warnings"])
        self.assertIn("cycle 1 stops before a later cycle", status["warnings"])

    def test_cycle_summary_reports_only_latest_open_work(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/2\n- Decision: continue\n- Changed: shared\n- Verified: first\n- Remaining: old work\n\n"
            "## 10:10 Two\n- Cycle: 2/2\n- Decision: stop_success\n- Changed: shared\n- Verified: second\n- Remaining: none\n",
            encoding="utf-8",
        )
        summary = build_cycle_summary(self.root, limit=1)
        self.assertEqual("stop_success", summary["latest_decision"])
        self.assertEqual([], summary["open_remaining"])
        self.assertEqual(1, summary["recent_changed"].count("shared"))

    def test_cycle_writer_rejects_continue_at_final_budget(self) -> None:
        path = self.root / "Harness/work/cycles/iteration.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/2\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        errors = validate_iteration_entry(path, cycle_number=2, max_cycles=2, decision="continue")
        self.assertIn("the final budgeted cycle must use stop_success or stop_blocked", errors)

    def test_cycle_writer_supports_legacy_unnumbered_log(self) -> None:
        path = self.root / "Harness/work/cycles/legacy.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 Old entry\n- Changed: legacy\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        self.assertEqual([], validate_iteration_entry(path, cycle_number=2, max_cycles=None, decision=""))

    def test_cycle_writer_rejects_existing_invalid_sequence(self) -> None:
        path = self.root / "Harness/work/cycles/invalid.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/4\n- Decision: continue\n- Verified: test\n- Remaining: next\n\n"
            "## 10:10 Three\n- Cycle: 3/4\n- Decision: continue\n- Verified: test\n- Remaining: next\n",
            encoding="utf-8",
        )
        errors = validate_iteration_entry(path, cycle_number=3, max_cycles=4, decision="continue")
        self.assertTrue(any("not a contiguous" in error for error in errors))

    def test_iteration_status_stops_on_repeated_remaining(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        entry = "- Cycle: {number}/5\n- Decision: continue\n- Changed: attempt {number}\n- Verified: test\n- Remaining: same blocker\n"
        path.write_text("## 10:00 One\n" + entry.format(number=1) + "\n## 10:10 Two\n" + entry.format(number=2), encoding="utf-8")
        report = build_iteration_status(self.root, request="up to 5 cycles", task="repeat")
        self.assertTrue(report["repeated_remaining"])
        self.assertIn("same_remaining_repeated_twice", report["stop_reasons"])
        self.assertFalse(report["continue_recommended"])

    def test_iteration_status_stops_on_invalid_cycle_log(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(
            "## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n\n"
            "## 10:10 Three\n- Cycle: 3/3\n- Decision: continue\n- Verified: test\n- Remaining: finish\n",
            encoding="utf-8",
        )
        report = build_iteration_status(self.root, request="3 cycles", task="repeat")
        self.assertIn("cycle numbers are not a contiguous 1-based sequence", report["cycle_log_warnings"])
        self.assertFalse(report["continue_recommended"])

    def test_handoff_uses_filtered_next_and_iteration_progress(self) -> None:
        path = self.root / "Harness/work/cycles/repeat.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("## 10:00 One\n- Cycle: 1/3\n- Decision: continue\n- Verified: test\n- Remaining: next\n", encoding="utf-8")
        handoff = build_handoff(self.root, request="3 cycles dashboard input", task="repeat")
        self.assertIn("## Iteration", handoff)
        self.assertIn("- Progress: 1/3", handoff)
        self.assertIn("- Repair dashboard input routing.", handoff)
        self.assertNotIn("- Verify terrain export bounds.", handoff)

    def test_knowledge_routes_retained_docs_and_task_records(self) -> None:
        docs = self.root / "Harness/docs"
        tasks = self.root / "Harness/work/tasks"
        docs.mkdir(exist_ok=True)
        tasks.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "LockOn.md").write_text("# Lock-on Recovery\n\nLegacy lock-on retry evidence.\n", encoding="utf-8")
        (tasks / "lock-on.md").write_text("# Task: lock-on\n\n- Remaining: verify legacy retry\n", encoding="utf-8")
        report = build_knowledge(self.root, query="legacy lock-on retry")
        kinds = {item["kind"] for item in report["matches"]}
        self.assertIn("doc", kinds)
        self.assertIn("task", kinds)
        context = build_context(self.root, request="legacy lock-on retry")
        self.assertTrue(any(item["path"].endswith("LockOn.md") for item in context["existing_knowledge"]["matches"]))

    def test_update_plan_preserves_project_data_and_stages_review_files(self) -> None:
        template = self.root / "new-template"
        target = self.root / "old-project"
        for base in [template, target]:
            (base / "Harness/config").mkdir(parents=True)
            (base / "Harness/docs").mkdir(parents=True)
            (base / "Harness/scripts/tools").mkdir(parents=True)
        for name in ["HARNESS.md", "AGENTS.md", "CLAUDE.md", "INSTALL.md"]:
            (template / name).write_text(f"new {name}\n", encoding="utf-8")
        (template / "Harness/README.md").write_text("new readme\n", encoding="utf-8")
        (template / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        (template / "Harness/config/docs.json").write_text('{"doc_roots": []}\n', encoding="utf-8")
        (template / "Harness/docs/Guide.md").write_text("new guide\n", encoding="utf-8")
        (template / "Harness/scripts/tools/standard.py").write_text("NEW = 1\n", encoding="utf-8")
        (target / "HARNESS.md").write_text("project rules\n", encoding="utf-8")
        (target / "Harness/config/project.json").write_text('{"project_name": "KeepMe"}\n', encoding="utf-8")
        (target / "Harness/docs/Guide.md").write_text("project knowledge\n", encoding="utf-8")
        (target / "Harness/scripts/tools/standard.py").write_text("OLD = 1\n", encoding="utf-8")
        (target / "Harness/scripts/tools/custom.py").write_text("CUSTOM = 1\n", encoding="utf-8")
        plan = build_update_plan(template, target)
        actions = {item["path"]: item["action"] for item in plan["actions"]}
        self.assertEqual("preserve", actions["Harness/config/project.json"])
        self.assertEqual("preserve", actions["Harness/docs/Guide.md"])
        self.assertEqual("merge_review", actions["HARNESS.md"])
        self.assertEqual("replace_review", actions["Harness/scripts/tools/standard.py"])
        self.assertIn("Harness/scripts/tools/custom.py", plan["custom_tools"])
        copied = apply_missing_files(template, target, plan)
        self.assertIn("CLAUDE.md", copied)
        self.assertIn("KeepMe", (target / "Harness/config/project.json").read_text(encoding="utf-8"))
        stage = self.root / "review"
        staged = stage_review_files(template, stage, plan)
        self.assertIn("HARNESS.md", staged)
        self.assertIn("Harness/scripts/tools/standard.py", staged)


    def test_diff_guard_standard_prefixes_do_not_contain_project_paths(self) -> None:
        known_standard = {"Source/", "Config/", "Content/", "Plugins/", "Harness/scripts/unreal/"}
        unexpected = [p for p in PROGRESS_TRIGGER_PREFIXES if p not in known_standard]
        self.assertEqual([], unexpected, f"non-standard prefixes in PROGRESS_TRIGGER_PREFIXES: {unexpected}")

    def test_docs_check_skip_hints_take_priority_over_read_hints(self) -> None:
        from harness_docs_check import evaluate_request
        docs_config = {"request_hints": {"read": ["level"], "skip": ["compile error"]}}
        result = evaluate_request("fix level compile error", docs_config)
        self.assertFalse(result["should_read_docs"])
        self.assertTrue(result["read_hits"])
        self.assertTrue(result["skip_hits"])

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


if __name__ == "__main__":
    unittest.main()
