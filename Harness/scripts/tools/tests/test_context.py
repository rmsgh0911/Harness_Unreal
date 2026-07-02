"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class ContextTests(HarnessBaseTestCase):
    def test_context_all_next_preserves_file_order(self) -> None:
        context = build_context(self.root, request="unrelated request", all_next=True)
        self.assertEqual(
            ["Repair dashboard input routing.", "Verify terrain export bounds."],
            context["next_items"],
        )
    def test_context_does_not_match_api_inside_capital(self) -> None:
        context = build_context(self.root, request="capital budget")
        self.assertNotIn("Harness/index/api_surface.md", context["project_index"]["recommended_first_reads"])
    def test_context_recommends_rulebook_only_when_task_needs_it(self) -> None:
        (self.root / "Harness/config/project.json").write_text(
            '{"template_mode": false, "project_name": "Demo", "uproject_file": "Demo.uproject"}\n',
            encoding="utf-8",
        )
        routine = build_context(self.root, request="Fix dashboard input")
        self.assertNotIn("HARNESS.md", routine["recommended_first_reads"])
        self.assertNotIn("Harness/README.md", routine["recommended_first_reads"])
        cycles = build_context(self.root, request="Improve lock-on, up to 3 cycles")
        self.assertIn("HARNESS.md", cycles["recommended_first_reads"])
        update = build_context(self.root, request="Harness update from the new template")
        self.assertIn("HARNESS.md", update["recommended_first_reads"])
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        unconnected = build_context(self.root, request="Fix dashboard input")
        self.assertIn("Harness/README.md", unconnected["recommended_first_reads"])

    def test_context_filters_unrelated_next_items(self) -> None:
        context = build_context(self.root, request="Fix dashboard input")
        self.assertEqual(["Repair dashboard input routing."], context["next_items"])
        self.assertEqual("Dashboard", context["project_index"]["matched_sections"][0]["section"])
        route = context["project_index"]["matched_sections"][0]
        self.assertEqual(["Source/UI/Dashboard.cpp"], route["paths"])
        self.assertEqual(["python verify_dashboard.py"], route["verification"])
    def test_context_includes_bounded_memory_hints(self) -> None:
        args = argparse.Namespace(
            id="00000000-0000-4000-8000-000000000126",
            created_at="2026-07-04T12:00:00+09:00",
            status="confirmed",
            title="Private Gitea memory",
            body="Daily JSONL shards may be committed in private repositories after review.",
            tags="memory,gitea",
            source="Harness/data/README.md",
        )
        add_memory_entry(self.root, args)
        context = build_context(self.root, request="private Gitea memory shards")
        hints = context["existing_knowledge"].get("memory_matches", [])
        self.assertEqual(1, len(hints))
        self.assertEqual("Private Gitea memory", hints[0]["title"])
        limited = build_context(self.root, request="private Gitea memory shards", use_memory=False)
        self.assertEqual([], limited["existing_knowledge"].get("memory_matches"))
    def test_context_keeps_explicit_api_routing_hint(self) -> None:
        context = build_context(self.root, request="API 변경")
        self.assertIn("Harness/index/api_surface.md", context["project_index"]["recommended_first_reads"])
    def test_context_keeps_file_priority_for_multiple_matches(self) -> None:
        context = build_context(self.root, request="Verify dashboard input and terrain export bounds")
        self.assertEqual(
            ["Repair dashboard input routing.", "Verify terrain export bounds."],
            context["next_items"],
        )
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
    def test_harness_update_context_routes_to_install_guide(self) -> None:
        (self.root / "Harness/docs/template").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/template/setup.md").write_text("# Install\n", encoding="utf-8")
        context = build_context(self.root, request="older Harness update")
        self.assertIn("Harness/docs/template/setup.md", context["recommended_first_reads"])
        self.assertFalse(context["cycle_policy"]["request_eval"]["is_cycle_work"])
    def test_korean_loop_word_does_not_trigger_iteration_mode(self) -> None:
        policy = {"default_max_cycles": 1, "cycle_count_rules": {"phrases": ["cycle", "cycles", "반복"]}}
        self.assertFalse(evaluate_cycle_request("반복문 오류 수정", policy)["is_cycle_work"])
        self.assertTrue(evaluate_cycle_request("검증을 반복해줘", policy)["is_cycle_work"])
