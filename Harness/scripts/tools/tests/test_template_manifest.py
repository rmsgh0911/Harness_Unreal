"""Regression tests for template ownership and deterministic release inventory."""

from _harness_test_base import *  # noqa: F401,F403

from harness_template_manifest import build_manifest, build_report as build_manifest_report
from harness_template_manifest import classify_owner, discover_release_files, release_bytes, release_files_from_manifest, write_manifest


class TemplateManifestTests(HarnessBaseTestCase):
    def test_release_hashes_survive_checkout_newlines_but_detect_content_changes(self) -> None:
        script = self.root / "Harness/harness.ps1"
        script.write_bytes(b"Write-Output 'ready'\n")
        write_manifest(self.root)
        script.write_bytes(b"Write-Output 'ready'\r\n")
        self.assertTrue(build_manifest_report(self.root)["ok"])
        script.write_bytes(b"Write-Output 'different'\r\n")
        self.assertFalse(build_manifest_report(self.root)["ok"])

    def test_release_bytes_preserve_unknown_and_binary_data(self) -> None:
        for name, content in [("blob.bin", b"a\r\nb"), ("invalid.txt", b"\xff\r\n"), ("nul.txt", b"a\x00\r\n")]:
            path = self.root / name
            path.write_bytes(content)
            self.assertEqual(content, release_bytes(path))

    def _seed_extensions(self) -> None:
        (self.root / "Harness/template").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/config/project.json").write_text("{}\n", encoding="utf-8")
        (self.root / "Harness/config/generated_artifacts.json").write_text('{"schema_version":1,"artifacts":[]}\n', encoding="utf-8")
        (self.root / "Harness/config/local_rules.md").write_text("# Local Rules\n", encoding="utf-8")
        (self.root / "Harness/docs/project").mkdir(parents=True, exist_ok=True)
        (self.root / "Harness/docs/project/README.md").write_text("# Project Docs\n", encoding="utf-8")

    def test_default_ownership_keeps_project_state_out_of_replacement_hashes(self) -> None:
        self._seed_extensions()
        manifest = build_manifest(self.root)

        self.assertEqual("project_owned", classify_owner("Harness/config/project.json", manifest["ownership_rules"]))
        self.assertEqual("project_owned", classify_owner("Harness/config/generated_artifacts.json", manifest["ownership_rules"]))
        self.assertEqual("managed_merge", classify_owner("HARNESS.md", manifest["ownership_rules"]))
        self.assertEqual("managed_merge", classify_owner("Harness/README.md", manifest["ownership_rules"]))
        self.assertIn("Harness/config/project.json", manifest["release_files"])
        self.assertNotIn("Harness/config/project.json", manifest["template_file_hashes"])
        self.assertIn("HARNESS.md", manifest["template_file_hashes"])

    def test_manifest_generation_is_deterministic(self) -> None:
        self._seed_extensions()
        first = build_manifest(self.root)
        second = build_manifest(self.root)

        self.assertEqual(first, second)

    def test_discovery_prunes_managed_runtime_before_descending(self) -> None:
        harness = self.root / "Harness"

        def guarded_walk(top, *, topdown, followlinks):
            self.assertEqual(harness, Path(top))
            self.assertTrue(topdown)
            self.assertFalse(followlinks)
            directory_names = [".runtime", "docs"]
            yield str(harness), directory_names, []
            if ".runtime" in directory_names:
                raise AssertionError("managed runtime was not pruned")
            yield str(harness / "docs"), [], []

        with patch("harness_template_manifest.os.walk", new=guarded_walk):
            discover_release_files(self.root)

    def test_written_manifest_is_current_and_controls_package_inventory(self) -> None:
        self._seed_extensions()
        write_manifest(self.root)

        report = build_manifest_report(self.root)
        packaged = {path.relative_to(self.root).as_posix() for path in release_files_from_manifest(self.root)}

        self.assertTrue(report["ok"], report["issues"])
        self.assertIn("Harness/template/manifest.json", packaged)
        self.assertIn("Harness/docs/project/README.md", packaged)

    def test_package_inventory_contains_python_free_bootstrap_surface(self) -> None:
        harness = self.root / "Harness"
        for name in ("bootstrap.ps1", "bootstrap.sh", "harness.cmd", "harness.ps1", "harness.sh"):
            (harness / name).write_text(f"{name}\n", encoding="utf-8")
        self._seed_extensions()
        write_manifest(self.root)

        packaged = {path.relative_to(self.root).as_posix() for path in release_files_from_manifest(self.root)}

        self.assertTrue(
            {
                "Harness/bootstrap.ps1",
                "Harness/bootstrap.sh",
                "Harness/harness.cmd",
                "Harness/harness.ps1",
                "Harness/harness.sh",
            }.issubset(packaged)
        )

    def test_new_unlisted_file_makes_manifest_stale_and_is_not_silently_packaged(self) -> None:
        self._seed_extensions()
        write_manifest(self.root)
        unexpected = self.root / "Harness/docs/unreviewed.md"
        unexpected.write_text("not accepted yet\n", encoding="utf-8")

        report = build_manifest_report(self.root)
        packaged = {path.relative_to(self.root).as_posix() for path in release_files_from_manifest(self.root)}

        self.assertFalse(report["ok"])
        self.assertNotIn("Harness/docs/unreviewed.md", packaged)
        self.assertTrue(any(item["message"] == "release_inventory_stale" for item in report["issues"]))
