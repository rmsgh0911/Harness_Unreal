from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from harness_context import build_context  # noqa: E402
from harness_context import evaluate_cycle_request  # noqa: E402
from harness_archive import apply_archive, build_plan as build_archive_plan, validate_archive_month  # noqa: E402
from harness_cycle import build_entry, validate_iteration_entry  # noqa: E402
from harness_cycle_summary import analyze_iteration, build_summary as build_cycle_summary, parse_cycle_file  # noqa: E402
from harness_diff_guard import PROGRESS_TRIGGER_PREFIXES  # noqa: E402
from harness_docs_check import REQUEST_READ_HINTS, REQUEST_SKIP_HINTS  # noqa: E402
from harness_index_check import build_report as build_index_report  # noqa: E402
from harness_iteration_status import build_status as build_iteration_status  # noqa: E402
from harness_handoff import build_handoff  # noqa: E402
from harness_knowledge import build_knowledge  # noqa: E402
from harness_progress_check import build_report as build_progress_report  # noqa: E402
from harness_release_check import build_report as build_release_report  # noqa: E402
from harness_release_pack import build_package, collect_files as collect_release_files, should_include as should_include_release_file  # noqa: E402
from harness_state_check import build_report as build_state_report  # noqa: E402
from harness_update_plan import apply_missing_files, build_update_plan, stage_review_files  # noqa: E402
from harness_verify_all import check_build_readiness, required_checks_ok  # noqa: E402


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

    def test_context_does_not_match_api_inside_capital(self) -> None:
        context = build_context(self.root, request="capital budget")
        self.assertNotIn("Harness/index/api_surface.md", context["project_index"]["recommended_first_reads"])

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

    def test_korean_loop_word_does_not_trigger_iteration_mode(self) -> None:
        policy = {"default_max_cycles": 1, "cycle_count_rules": {"phrases": ["cycle", "cycles", "반복"]}}
        self.assertFalse(evaluate_cycle_request("반복문 오류 수정", policy)["is_cycle_work"])
        self.assertTrue(evaluate_cycle_request("검증을 반복해줘", policy)["is_cycle_work"])

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

    def test_archive_rejects_invalid_month_in_library_calls(self) -> None:
        with self.assertRaises(ValueError):
            validate_archive_month("../../outside")
        with self.assertRaises(ValueError):
            build_archive_plan(self.root, "safe-task", "../../outside")

    def test_archive_rolls_back_when_second_move_fails(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        cycles = self.root / "Harness/work/cycles"
        tasks.mkdir()
        cycles.mkdir()
        task = tasks / "rollback-task.md"
        cycle = cycles / "rollback-task.md"
        task.write_text("# Task\n\n- Status: completed\n", encoding="utf-8")
        cycle.write_text("# Cycle\n", encoding="utf-8")
        plan = build_archive_plan(self.root, "rollback-task", "2026-06")
        from harness_archive import shutil as archive_shutil
        real_move = archive_shutil.move

        def fail_cycle_move(source: Path, target: Path):
            if Path(source) == cycle:
                raise OSError("simulated second move failure")
            return real_move(source, target)

        with patch("harness_archive.shutil.move", side_effect=fail_cycle_move):
            with self.assertRaises(OSError):
                apply_archive(self.root, plan)
        self.assertTrue(task.exists())
        self.assertTrue(cycle.exists())
        self.assertFalse((self.root / "Harness/work/archive/2026-06/tasks/rollback-task.md").exists())
        self.assertFalse((self.root / "Harness/work/archive/index.md").exists())
        self.assertFalse((self.root / "Harness/work/archive").exists())

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

    def test_knowledge_does_not_match_tokens_inside_unrelated_words(self) -> None:
        docs = self.root / "Harness/docs"
        docs.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "Budget.md").write_text("# Capital Budget\n\nFinance only.\n", encoding="utf-8")
        report = build_knowledge(self.root, query="api")
        self.assertFalse(any(item["path"].endswith("Budget.md") for item in report["matches"]))

    def test_korean_particles_do_not_hide_relevant_knowledge(self) -> None:
        docs = self.root / "Harness/docs"
        docs.mkdir(exist_ok=True)
        (self.root / "Harness/config/docs.json").write_text('{"doc_roots": ["Harness/docs"]}\n', encoding="utf-8")
        (docs / "Dashboard.md").write_text("# 대시보드 UI 경로\n\n위젯 수정 안내.\n", encoding="utf-8")
        report = build_knowledge(self.root, query="대시보드를 수정해줘")
        self.assertTrue(any(item["path"].endswith("Dashboard.md") for item in report["matches"]))
        context = build_context(self.root, request="대시보드를 수정해줘")
        self.assertTrue(any(item["path"].endswith("Dashboard.md") for item in context["existing_knowledge"]["matches"]))

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

    def test_update_apply_requires_existing_harness_target(self) -> None:
        missing_target = self.root / "typo-target"
        plan = build_update_plan(self.root, missing_target)
        with self.assertRaises(ValueError):
            apply_missing_files(self.root, missing_target, plan)
        self.assertFalse(missing_target.exists())

    def test_update_plan_rejects_invalid_template_root(self) -> None:
        missing_template = self.root / "missing-template"
        with self.assertRaises(ValueError):
            build_update_plan(missing_template, self.root)

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

    def test_release_excludes_and_flags_archived_work_records(self) -> None:
        archived = self.root / "Harness/work/archive/2026-06/tasks/customer-task.md"
        nested_readme = self.root / "Harness/work/archive/2026-06/tasks/README.md"
        task_sidecar = self.root / "Harness/work/tasks/nested/evidence.json"
        cycle_sidecar = self.root / "Harness/work/cycles/nested/log.txt"
        archived.parent.mkdir(parents=True)
        archived.write_text("customer history\n", encoding="utf-8")
        nested_readme.write_text("archived task named README\n", encoding="utf-8")
        task_sidecar.parent.mkdir(parents=True)
        cycle_sidecar.parent.mkdir(parents=True)
        task_sidecar.write_text("{}\n", encoding="utf-8")
        cycle_sidecar.write_text("private cycle evidence\n", encoding="utf-8")
        packaged = {path.relative_to(self.root).as_posix() for path in collect_release_files(self.root)}
        for path in [archived, nested_readme, task_sidecar, cycle_sidecar]:
            self.assertNotIn(path.relative_to(self.root).as_posix(), packaged)
        report = build_release_report(self.root, strict=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["message"].startswith("archived_work_records_present:") for item in report["warnings"]))
        self.assertTrue(any(item["message"].startswith("real_task_records_present:") for item in report["warnings"]))
        self.assertTrue(any(item["message"].startswith("cycle_logs_present:") for item in report["warnings"]))

    def test_release_detects_project_doc_paths_across_script_types_and_quotes(self) -> None:
        scripts = self.root / "Harness/scripts"
        (scripts / "tools").mkdir(parents=True, exist_ok=True)
        (scripts / "unreal").mkdir(parents=True, exist_ok=True)
        leaked_path = "Harness/docs/" + "SecretProject/"
        leaked_file_path = leaked_path + "design.md"
        (scripts / "tools/single.py").write_text(f"P = '{leaked_path}'\n", encoding="utf-8")
        (scripts / "unreal/leak.ps1").write_text(f'$P = "{leaked_file_path}"\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        leaked_files = {item["path"] for item in report["errors"] if item["message"].startswith("hardcoded_project_doc_path_in_script:")}
        self.assertEqual({"Harness/scripts/tools/single.py", "Harness/scripts/unreal/leak.ps1"}, leaked_files)

    def test_release_detects_project_doc_folder_with_non_letter_prefix(self) -> None:
        script = self.root / "Harness/scripts/tools/leak.py"
        leaked_path = "Harness/docs/" + "2026프로젝트/design.md"
        script.write_text(f'PATH = "{leaked_path}"\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["path"].endswith("leak.py") for item in report["errors"]))

    def test_release_allows_generic_doc_glob_in_tool_manifest(self) -> None:
        manifest = self.root / "Harness/scripts/tools/tool_manifest.json"
        manifest.write_text('{"inputs": ["Harness/docs/**/*.md"]}\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertFalse(any(item["path"].endswith("tool_manifest.json") for item in report["errors"]))

    def test_release_pack_blocks_write_until_strict_check_passes(self) -> None:
        script = self.root / "Harness/scripts/tools/leak.py"
        leaked_path = "Harness/docs/" + "_Private/design.md"
        script.write_text(f'PATH = "{leaked_path}"\n', encoding="utf-8")
        output = self.root / "release.zip"
        report = build_package(self.root, output, write=True)
        self.assertFalse(report["ok"])
        self.assertTrue(report["blocked"])
        self.assertFalse(output.exists())
        forced = build_package(self.root, output, write=True, force=True)
        self.assertTrue(forced["ok"])
        self.assertTrue(output.exists())

    def test_release_pack_refuses_to_overwrite_template_source(self) -> None:
        harness_file = self.root / "HARNESS.md"
        original = harness_file.read_bytes()
        report = build_package(self.root, harness_file, write=True)
        self.assertFalse(report["ok"])
        self.assertIn("output_must_use_zip_extension", report["output_errors"])
        self.assertIn("output_would_overwrite_packaged_source", report["output_errors"])
        self.assertEqual(original, harness_file.read_bytes())
        harness_output = build_package(self.root, self.root / "Harness/release.zip", write=True)
        self.assertFalse(harness_output["ok"])
        self.assertIn("output_must_be_outside_harness_tree", harness_output["output_errors"])

    def test_release_pack_excludes_symlink_candidates(self) -> None:
        candidate = self.root / "Harness/linked.md"
        with patch.object(Path, "is_symlink", return_value=True):
            self.assertFalse(should_include_release_file(candidate, self.root))

    def test_release_rejects_and_excludes_symlinks(self) -> None:
        external = self.root.parent / f"{self.root.name}-external.txt"
        link = self.root / "Harness/docs-link.md"
        external.write_text("external content\n", encoding="utf-8")
        try:
            try:
                link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            report = build_release_report(self.root, strict=True)
            self.assertTrue(any(item["message"] == "template_symlink_not_allowed" for item in report["errors"]))
            self.assertNotIn(link, collect_release_files(self.root))
        finally:
            if link.exists() or link.is_symlink():
                link.unlink()
            if external.exists():
                external.unlink()

    def test_release_pack_preserves_existing_zip_when_write_fails(self) -> None:
        output = self.root / "existing.zip"
        output.write_bytes(b"existing package")
        with patch("harness_release_pack.zipfile.ZipFile.write", side_effect=OSError("simulated zip failure")):
            with self.assertRaises(OSError):
                build_package(self.root, output, write=True)
        self.assertEqual(b"existing package", output.read_bytes())

    def test_project_build_readiness_is_a_required_verification_gate(self) -> None:
        (self.root / "Harness/config/project.json").write_text(
            '{"template_mode": false, "uproject_file": "", "build": {}}\n',
            encoding="utf-8",
        )
        readiness = check_build_readiness(self.root)
        self.assertFalse(readiness["ok"])
        self.assertFalse(required_checks_ok({"ok": True}, readiness))

    def test_release_rejects_activity_filled_progress_in_template_mode(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["message"] == "template_progress_contains_project_activity" for item in report["errors"]))

    def test_release_progress_neutrality_cannot_be_bypassed_by_marker_count(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        marker = "작성 필요"
        (self.root / "Harness/Progress.md").write_text(
            "# Progress\n" + " ".join([marker] * 4) + "\n## 현재 상태\n- 실제 고객 프로젝트 완료\n",
            encoding="utf-8",
        )
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["message"] == "template_progress_contains_project_activity" for item in report["errors"]))

    def test_release_progress_rejects_extra_activity_bullet(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        progress = """# Progress

## 현재 상태
- 작성 필요: 현재 상태를 기록합니다.
- 실제 고객 프로젝트 작업 완료

## 최근 완료
- 작성 필요: 최근 완료를 기록합니다.

## 확인 필요
- 작성 필요: 확인 필요를 기록합니다.

## 다음 작업
- 작성 필요: 다음 작업을 기록합니다.
"""
        (self.root / "Harness/Progress.md").write_text(progress, encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["message"] == "template_progress_contains_project_activity" for item in report["errors"]))

    def test_task_template_uses_provider_neutral_branch_placeholder(self) -> None:
        root = TOOLS_DIR.parents[2]
        task_example = (root / "Harness/work/tasks/task.example.md").read_text(encoding="utf-8")
        self.assertIn("- Branch: <agent>/example-task", task_example)
        self.assertNotIn("- Branch: codex/", task_example)


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

    def test_docs_check_does_not_match_format_inside_information(self) -> None:
        from harness_docs_check import evaluate_request
        docs_config = {"request_hints": {"read": ["design"], "skip": ["format"]}, "entry_points": ["Harness/docs/README.md"]}
        result = evaluate_request("information architecture design", docs_config)
        self.assertTrue(result["should_read_docs"])
        self.assertEqual([], result["skip_hits"])

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
