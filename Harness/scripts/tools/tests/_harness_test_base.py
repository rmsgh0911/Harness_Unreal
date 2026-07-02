from __future__ import annotations

import argparse
import json
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
from harness_archive import apply_archive, build_before_plan as build_archive_before_plan, build_plan as build_archive_plan, validate_archive_month  # noqa: E402
from harness_cycle import build_entry, validate_iteration_entry  # noqa: E402
from harness_cycle_summary import analyze_iteration, build_summary as build_cycle_summary, parse_cycle_file  # noqa: E402
from harness_diff_guard import PROGRESS_TRIGGER_PREFIXES  # noqa: E402
from harness_docs_check import REQUEST_READ_HINTS, REQUEST_SKIP_HINTS  # noqa: E402
from harness_field_check import build_report as build_field_report  # noqa: E402
from harness_index_check import build_report as build_index_report  # noqa: E402
from harness_iteration_status import build_status as build_iteration_status  # noqa: E402
from harness_handoff import build_handoff  # noqa: E402
from harness_knowledge import build_knowledge  # noqa: E402
from harness_memory import add_entry as add_memory_entry, memory_doctor, prune_memory, query_memory as query_memory_entries, rebuild_cache as rebuild_memory_cache, update_status as update_memory_status, validate_memory  # noqa: E402
from harness_progress_check import build_report as build_progress_report  # noqa: E402
from harness_progress_html import build_report as build_progress_html_report, build_server as build_progress_server  # noqa: E402
from harness_release_check import build_report as build_release_report  # noqa: E402
from harness_release_pack import build_package, collect_files as collect_release_files, should_include as should_include_release_file  # noqa: E402
from harness_state_check import build_report as build_state_report  # noqa: E402
from harness_unreal_risk import classify_path, idempotency_hints, pie_only_hints  # noqa: E402
from harness_doctor import run_doctor  # noqa: E402
from harness_update_plan import apply_missing_files, build_update_plan, stage_review_files  # noqa: E402
from harness_verify_all import check_build_readiness, compile_python_files, required_checks_ok  # noqa: E402
from harness_scan import scan  # noqa: E402
from harness_project_fill import build_report as build_project_fill_report, deep_fill  # noqa: E402
from harness_docs_index import build_index as build_docs_index  # noqa: E402
from harness_migration_audit import audit as migration_audit  # noqa: E402


VALID_PROGRESS = """# Progress

짧은 현재 대시보드입니다.

**Last updated:** 2026-07-02 14:30:45 +09:00

## 현재 상태

- 기능 A가 동작합니다.

## 최근 완료

- 기능 A 검증을 마쳤습니다.

## 확인 필요

- PIE 확인이 필요합니다.

## 다음 작업

- 기능 B를 구현합니다.
"""


class HarnessBaseTestCase(unittest.TestCase):
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
