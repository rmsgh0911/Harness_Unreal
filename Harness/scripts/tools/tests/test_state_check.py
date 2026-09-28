"""Regression tests split from the original test_structure_tools.py."""

from _harness_test_base import *  # noqa: F401,F403


class StateCheckTests(HarnessBaseTestCase):
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
    def test_state_check_warns_about_completed_next_item(self) -> None:
        path = self.root / "Harness/work/next.md"
        path.write_text("# Next\n\n## Active Work\n- [x] Old work\n- New work\n", encoding="utf-8")
        findings = build_state_report(self.root)["findings"]
        self.assertTrue(any("completed checklist items" in item["message"] and item.get("line") == 4 for item in findings))
    def test_state_check_warns_about_completed_task_records(self) -> None:
        tasks = self.root / "Harness/work/tasks"
        tasks.mkdir()
        (tasks / "done-task.md").write_text("# Task\n\n- Status: complete\n", encoding="utf-8")
        (tasks / "active-task.md").write_text("# Task\n\n- Status: active\n", encoding="utf-8")
        findings = build_state_report(self.root)["findings"]
        matches = [item for item in findings if "completed task records should be archived" in item["message"]]
        self.assertEqual(1, len(matches))
        self.assertIn("done-task", matches[0]["message"])
        self.assertNotIn("active-task", matches[0]["message"])
        self.assertIn("archive --task", matches[0]["message"])
        self.assertNotIn("python Harness/scripts/tools", matches[0]["message"])
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

    def test_warning_debt_ids_are_stable_and_strict_blocks_new_warning(self) -> None:
        path = self.root / "Harness/work/next.md"
        path.write_text("# Next\n\n## Active Work\n- [x] One old item\n", encoding="utf-8")
        first = build_state_report(self.root, strict=True)
        finding = next(item for item in first["findings"] if "completed checklist" in item["message"])
        self.assertEqual("new", finding["debt_status"])
        self.assertFalse(first["ok"])
        path.write_text("# Next\n\n\n## Active Work\n- [x] Two old items\n", encoding="utf-8")
        second = build_state_report(self.root, strict=True)
        changed_line = next(item for item in second["findings"] if "completed checklist" in item["message"])
        self.assertEqual(finding["id"], changed_line["id"])

    def test_unexpired_warning_baseline_is_visible_but_not_strict_blocking(self) -> None:
        (self.root / "Harness/work/next.md").write_text("# Next\n\n## Active Work\n- [x] Old item\n", encoding="utf-8")
        finding = next(item for item in build_state_report(self.root)["findings"] if "completed checklist" in item["message"])
        (self.root / "Harness/config/record_policy.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "warning_baseline": [
                        {"id": finding["id"], "reason": "migration cleanup", "expires": "2099-12-31"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        report = build_state_report(self.root, strict=True)
        accepted = next(item for item in report["findings"] if item["id"] == finding["id"])
        self.assertTrue(report["ok"])
        self.assertEqual("baseline", accepted["debt_status"])

    def test_expired_warning_baseline_blocks_strict_mode(self) -> None:
        (self.root / "Harness/work/next.md").write_text("# Next\n\n## Active Work\n- [x] Old item\n", encoding="utf-8")
        finding = next(item for item in build_state_report(self.root)["findings"] if "completed checklist" in item["message"])
        (self.root / "Harness/config/record_policy.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "warning_baseline": [
                        {"id": finding["id"], "reason": "expired migration cleanup", "expires": "2000-01-01"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        report = build_state_report(self.root, strict=True)
        self.assertFalse(report["ok"])
        self.assertIn(finding["id"], report["warning_debt"]["expired"])
