"""Regression tests for secret-safe sensitive text scanning."""

from _harness_test_base import *  # noqa: F401,F403

from harness_sensitive_check import build_report as build_sensitive_report
from harness_sensitive_check import format_text as format_sensitive_text
from harness_sensitive_check import normalized_line_sha256


class SensitiveCheckTests(HarnessBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.root / "Harness/config/sensitive_allowlist.json").write_text(
            '{"schema_version": 1, "entries": []}\n',
            encoding="utf-8",
        )

    def test_high_confidence_value_is_blocking_and_never_echoed(self) -> None:
        secret = "ghp_" + "A" * 36
        document = self.root / "Harness/docs/security.md"
        document.parent.mkdir(parents=True)
        document.write_text(f"token={secret}\n", encoding="utf-8")

        report = build_sensitive_report(self.root)
        rendered = json.dumps(report, ensure_ascii=False) + format_sensitive_text(report)

        self.assertFalse(report["ok"])
        self.assertTrue(any(item["rule_id"] == "github_token" for item in report["findings"]))
        self.assertNotIn(secret, rendered)

    def test_missing_allowlist_keeps_older_install_scannable(self) -> None:
        (self.root / "Harness/config/sensitive_allowlist.json").unlink()

        report = build_sensitive_report(self.root)

        self.assertTrue(report["ok"])
        self.assertFalse(any(item["rule_id"] == "allowlist_missing" for item in report["findings"]))

    def test_placeholders_pass_and_ambiguous_assignment_is_strict_only(self) -> None:
        document = self.root / "Harness/docs/configuration.md"
        document.parent.mkdir(parents=True)
        document.write_text(
            "api_key = ${API_KEY}\npassword = replace_me\nclient_secret = plausible-secret-value\n",
            encoding="utf-8",
        )

        normal = build_sensitive_report(self.root)
        strict = build_sensitive_report(self.root, strict=True)

        self.assertTrue(normal["ok"])
        self.assertEqual(1, normal["summary"]["warnings"])
        self.assertFalse(strict["ok"])

    def test_allowlist_uses_normalized_line_hash_and_value_change_invalidates_it(self) -> None:
        first_secret = "ghp_" + "B" * 36
        second_secret = "ghp_" + "C" * 36
        line = f"token = {first_secret}"
        document = self.root / "Harness/docs/accepted.md"
        document.parent.mkdir(parents=True)
        document.write_text(line + "\n", encoding="utf-8")
        allowlist = {
            "schema_version": 1,
            "entries": [
                {
                    "path": "Harness/docs/accepted.md",
                    "rule_id": "github_token",
                    "line_sha256": normalized_line_sha256("  token   =   " + first_secret),
                    "reason": "Synthetic regression fixture",
                    "expires": "2099-12-31"
                }
            ]
        }
        (self.root / "Harness/config/sensitive_allowlist.json").write_text(
            json.dumps(allowlist),
            encoding="utf-8",
        )

        allowed = build_sensitive_report(self.root)
        document.write_text(f"token = {second_secret}\n", encoding="utf-8")
        changed = build_sensitive_report(self.root)

        self.assertTrue(allowed["ok"])
        self.assertEqual(1, allowed["allowlisted_count"])
        self.assertFalse(changed["ok"])
        rendered = json.dumps(changed) + format_sensitive_text(changed)
        self.assertNotIn(second_secret, rendered)

    def test_expired_allowlist_is_reported_without_suppressing_match(self) -> None:
        secret = "AKIA" + "D" * 16
        line = f"credential={secret}"
        document = self.root / "Harness/docs/expired.md"
        document.parent.mkdir(parents=True)
        document.write_text(line + "\n", encoding="utf-8")
        allowlist = {
            "schema_version": 1,
            "entries": [
                {
                    "path": "Harness/docs/expired.md",
                    "rule_id": "aws_access_key",
                    "line_sha256": normalized_line_sha256(line),
                    "reason": "Expired synthetic fixture",
                    "expires": "2000-01-01"
                }
            ]
        }
        (self.root / "Harness/config/sensitive_allowlist.json").write_text(json.dumps(allowlist), encoding="utf-8")

        report = build_sensitive_report(self.root)

        self.assertFalse(report["ok"])
        self.assertTrue(any(item["rule_id"] == "allowlist_expired" for item in report["findings"]))
        self.assertTrue(any(item["rule_id"] == "aws_access_key" for item in report["findings"]))
