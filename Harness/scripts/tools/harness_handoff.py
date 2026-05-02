"""Build a compact handoff brief for another agent."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import (
    dump_json,
    find_project_root,
    harness_dir,
    markdown_list_items,
    read_text,
    rel,
    today_cycle_path,
    write_text,
)
from harness_context import build_context
from harness_diff_guard import build_report, changed_path_from_status


def tail_lines(text: str, limit: int = 30) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    return lines[-limit:]


def build_handoff(root: Path, request: str = "") -> str:
    harness = harness_dir(root)
    context = build_context(root)
    diff = build_report(root)
    cycle_text = read_text(today_cycle_path(root))
    next_text = read_text(harness / "next.md")

    lines = [
        "# Harness Handoff",
        "",
        f"- 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 루트: {root}",
        f"- 요청: {request or '작성 필요'}",
        f"- 프로젝트: {context['project']['name'] or 'not configured'}",
        f"- uproject: {context['project']['uproject_file'] or 'not configured'}",
        f"- git 사용 가능: {diff['git_available']}",
        f"- 변경 확인 모드: {diff['mode']}",
        f"- 변경 파일 수: {diff['changed_count'] if diff['change_list_reliable'] else 'git 없음, 제한 확인'}",
        f"- 위험 신호 수: {diff['risk_count']}",
        "",
        "## 먼저 읽을 것",
    ]
    lines.extend(f"- {item}" for item in context["recommended_first_reads"])

    lines.extend(["", "## 다음 작업"])
    next_items = markdown_list_items(next_text, limit=8)
    if next_items:
        lines.extend(f"- {item}" for item in next_items)
    else:
        lines.append("- 없음")

    lines.extend(["", "## 변경 파일"])
    if diff["changed"]:
        lines.extend(f"- {changed_path_from_status(item)}" for item in diff["changed"][:40])
    else:
        lines.append("- 감지된 변경 없음")

    lines.extend(["", "## 위험 신호"])
    if diff["risks"]:
        lines.extend(f"- [{item['level']}] {item['path']}: {item['reason']}" for item in diff["risks"])
    else:
        lines.append("- 없음")

    lines.extend(["", "## 오늘 사이클 마지막 기록"])
    cycle_tail = tail_lines(cycle_text, limit=30)
    if cycle_tail:
        lines.extend(cycle_tail)
    else:
        lines.append("- 오늘 사이클 로그 없음")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact Harness handoff brief.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--request", default="", help="Current user request or handoff reason.")
    parser.add_argument("--output", type=Path, default=None, help="Output path. Defaults to Harness/handoff.md.")
    parser.add_argument("--write", action="store_true", help="Write the handoff brief. Default is dry run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    output = args.output or (root / "Harness" / "handoff.md")
    text = build_handoff(root, args.request)
    result = {
        "root": str(root),
        "output": rel(output, root),
        "write": args.write,
        "status": "written" if args.write else "dry_run",
        "handoff": text,
    }
    if args.write:
        write_text(output, text)
        if args.json:
            print(dump_json(result))
        else:
            print(f"Wrote handoff brief: {output}")
    else:
        if args.json:
            print(dump_json(result))
        else:
            print(text.rstrip())
            print("")
            print(f"Dry run only. Add --write to write {output}")


if __name__ == "__main__":
    main()
