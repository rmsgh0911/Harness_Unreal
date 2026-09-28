"""Regression tests split from the original test_structure_tools.py."""

import os
import zipfile

from _harness_test_base import *  # noqa: F401,F403
from harness_template_manifest import write_manifest


class ReleaseTests(HarnessBaseTestCase):
    def test_package_bytes_survive_checkout_newline_changes(self) -> None:
        script = self.root / "Harness/harness.ps1"
        script.write_bytes(b"Write-Output 'ready'\n")
        write_manifest(self.root)
        first = self.root / "lf.zip"
        second = self.root / "crlf.zip"
        self.assertTrue(build_package(self.root, first, write=True)["ok"])
        script.write_bytes(b"Write-Output 'ready'\r\n")
        self.assertTrue(build_package(self.root, second, write=True)["ok"])
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_release_surfaces_invalid_generated_artifact_provenance(self) -> None:
        (self.root / "Harness/config/generated_artifacts.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": [{"id": "broken"}]}),
            encoding="utf-8",
        )
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["message"].startswith("generated_artifact_broken:") for item in report["errors"]))

    def test_release_excludes_and_rejects_workspace_temp_tree(self) -> None:
        temporary = self.root / "Harness/temp/review/private-proposal.md"
        temporary.parent.mkdir(parents=True)
        temporary.write_text("project-only review material\n", encoding="utf-8")

        packaged = {path.relative_to(self.root).as_posix() for path in collect_release_files(self.root)}
        report = build_release_report(self.root)

        self.assertNotIn("Harness/temp/review/private-proposal.md", packaged)
        self.assertFalse(report["ok"])
        self.assertIn(
            {"path": "Harness/temp/", "message": "workspace_only_tree_present:1"},
            report["errors"],
        )

    def test_release_allows_generic_doc_glob_in_tool_manifest(self) -> None:
        manifest = self.root / "Harness/scripts/tools/tool_manifest.json"
        manifest.write_text('{"inputs": ["Harness/docs/**/*.md"]}\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertFalse(any(item["path"].endswith("tool_manifest.json") for item in report["errors"]))
    def test_release_allows_standard_project_doc_root_in_tools(self) -> None:
        script = self.root / "Harness/scripts/tools/project_docs.py"
        script.write_text('PATH = "Harness/docs/project/**/*.md"\n', encoding="utf-8")

        report = build_release_report(self.root)

        self.assertFalse(any(item["path"].endswith("project_docs.py") for item in report["errors"]))
    def test_release_check_ignores_imported_reference_harness_copies(self) -> None:
        reference = self.root / "Harness_Customer-work1/work/cycles"
        reference.mkdir(parents=True)
        bom_file = reference / "claude-2026-05-21.md"
        bom_file.write_bytes(b"\xef\xbb\xbf# Cycle\n")
        report = build_release_report(self.root, strict=True)
        flagged = [item for item in [*report["errors"], *report["warnings"]] if "Harness_Customer-work1" in item["path"]]
        self.assertEqual([], flagged)
    def test_release_check_rejects_static_progress_html(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        (self.root / "Harness/Progress_index.html").write_text(
            "<html><body><section>Static progress snapshot</section></body></html>\n",
            encoding="utf-8",
        )

        report = build_release_report(self.root)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(item["message"] == "progress_html_not_dynamic_viewer" for item in report["errors"]),
            report["errors"],
        )
    def test_release_detects_project_doc_folder_with_non_letter_prefix(self) -> None:
        script = self.root / "Harness/scripts/tools/leak.py"
        leaked_path = "Harness/docs/" + "2026프로젝트/design.md"
        script.write_text(f'PATH = "{leaked_path}"\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["path"].endswith("leak.py") for item in report["errors"]))
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
    def test_release_pack_blocks_write_until_strict_check_passes(self) -> None:
        script = self.root / "Harness/scripts/tools/leak.py"
        leaked_path = "Harness/docs/" + "_Private/design.md"
        script.write_text(f'PATH = "{leaked_path}"\n', encoding="utf-8")
        write_manifest(self.root)
        output = self.root / "release.zip"
        report = build_package(self.root, output, write=True)
        self.assertFalse(report["ok"])
        self.assertTrue(report["blocked"])
        self.assertFalse(output.exists())
        forced = build_package(self.root, output, write=True, force=True)
        self.assertTrue(forced["ok"])
        self.assertTrue(output.exists())
    def test_release_pack_force_cannot_bypass_stale_manifest(self) -> None:
        write_manifest(self.root)
        unexpected = self.root / "Harness/docs/unreviewed.md"
        unexpected.parent.mkdir(parents=True, exist_ok=True)
        unexpected.write_text("not accepted yet\n", encoding="utf-8")
        output = self.root / "release.zip"

        report = build_package(self.root, output, write=True, force=True)

        self.assertFalse(report["ok"])
        self.assertTrue(report["blocked"])
        self.assertFalse(output.exists())
        self.assertTrue(
            any(item["message"] == "template_manifest_release_inventory_stale" for item in report["unforceable_errors"]),
            report,
        )
    def test_release_pack_requires_manifest_even_when_forced(self) -> None:
        output = self.root / "release.zip"

        report = build_package(self.root, output, write=True, force=True)

        self.assertFalse(report["ok"])
        self.assertTrue(report["blocked"])
        self.assertFalse(output.exists())
        self.assertIn(
            {
                "path": "Harness/template/manifest.json",
                "message": "template_manifest_required_for_release_pack",
            },
            report["unforceable_errors"],
        )
    def test_release_pack_force_cannot_bypass_malformed_manifest(self) -> None:
        manifest = self.root / "Harness/template/manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{not json\n", encoding="utf-8")
        output = self.root / "release.zip"

        report = build_package(self.root, output, write=True, force=True)

        self.assertFalse(report["ok"])
        self.assertTrue(report["blocked"])
        self.assertFalse(output.exists())
        self.assertTrue(
            any(item["message"] == "template_manifest_manifest_unreadable" for item in report["unforceable_errors"]),
            report,
        )
    def test_release_pack_is_reproducible_across_source_mtime_changes(self) -> None:
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        source = self.root / "HARNESS.md"
        write_manifest(self.root)

        first_report = build_package(self.root, first, write=True)
        os.utime(source, (1_600_000_000, 1_600_000_000))
        second_report = build_package(self.root, second, write=True)

        self.assertTrue(first_report["ok"], first_report)
        self.assertTrue(second_report["ok"], second_report)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as archive:
            entries = archive.infolist()
        self.assertEqual(sorted(entry.filename.casefold() for entry in entries), [entry.filename.casefold() for entry in entries])
        self.assertTrue(all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in entries))
        self.assertTrue(all(entry.compress_type == zipfile.ZIP_STORED for entry in entries))
    def test_release_pack_excludes_memory_cache_and_daily_shards(self) -> None:
        self.assertFalse(should_include_release_file(self.root / "Harness/data/harness.sqlite", self.root))
        self.assertFalse(should_include_release_file(self.root / "Harness/data/harness.sqlite-wal", self.root))
        self.assertFalse(should_include_release_file(self.root / "Harness/data/memory/2026-07-01.jsonl", self.root))
        self.assertTrue(should_include_release_file(self.root / "Harness/data/memory/.gitkeep", self.root))
    def test_release_ignores_project_local_managed_python_runtime(self) -> None:
        runtime_cache = self.root / "Harness/.runtime/linux-x86_64/python/lib/__pycache__"
        runtime_cache.mkdir(parents=True)
        runtime_pyc = runtime_cache / "runtime.pyc"
        runtime_pyc.write_bytes(b"managed runtime")

        packaged = {path.relative_to(self.root).as_posix() for path in collect_release_files(self.root)}
        report = build_release_report(self.root, strict=True)

        self.assertNotIn(runtime_pyc.relative_to(self.root).as_posix(), packaged)
        self.assertFalse(any(item["message"] == "generated_python_cache" for item in report["errors"]))
    def test_release_pack_excludes_symlink_candidates(self) -> None:
        candidate = self.root / "Harness/linked.md"
        with patch.object(Path, "is_symlink", return_value=True):
            self.assertFalse(should_include_release_file(candidate, self.root))
    def test_release_pack_preserves_existing_zip_when_write_fails(self) -> None:
        output = self.root / "existing.zip"
        output.write_bytes(b"existing package")
        write_manifest(self.root)
        with patch("harness_release_pack.zipfile.ZipFile.writestr", side_effect=OSError("simulated zip failure")):
            with self.assertRaises(OSError):
                build_package(self.root, output, write=True)
        self.assertEqual(b"existing package", output.read_bytes())
    def test_release_pack_refuses_to_overwrite_template_source(self) -> None:
        harness_file = self.root / "HARNESS.md"
        original = harness_file.read_bytes()
        write_manifest(self.root)
        report = build_package(self.root, harness_file, write=True)
        self.assertFalse(report["ok"])
        self.assertIn("output_must_use_zip_extension", report["output_errors"])
        self.assertIn("output_would_overwrite_packaged_source", report["output_errors"])
        self.assertEqual(original, harness_file.read_bytes())
        harness_output = build_package(self.root, self.root / "Harness/release.zip", write=True)
        self.assertFalse(harness_output["ok"])
        self.assertIn("output_must_be_outside_harness_tree", harness_output["output_errors"])
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
    def test_release_rejects_activity_filled_progress_in_template_mode(self) -> None:
        (self.root / "Harness/config/project.json").write_text('{"template_mode": true}\n', encoding="utf-8")
        report = build_release_report(self.root, strict=True)
        self.assertTrue(any(item["message"] == "template_progress_contains_project_activity" for item in report["errors"]))
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
