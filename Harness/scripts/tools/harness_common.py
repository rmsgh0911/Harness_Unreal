"""Shared helpers for small Harness CLI tools."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


HARNESS_DIR_NAME = "Harness"
WORK_DIR_NAME = "work"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest parent that looks like a Harness project root."""
    current = (start or Path.cwd()).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "HARNESS.md").exists() and (candidate / HARNESS_DIR_NAME).is_dir():
            return candidate
    return current


def harness_dir(root: Path) -> Path:
    return root / HARNESS_DIR_NAME


def work_dir(root: Path) -> Path:
    return harness_dir(root) / WORK_DIR_NAME


def state_path(root: Path) -> Path:
    return work_dir(root) / "state.md"


def next_path(root: Path) -> Path:
    return work_dir(root) / "next.md"


def cycles_dir(root: Path) -> Path:
    return work_dir(root) / "cycles"


def tasks_dir(root: Path) -> Path:
    return work_dir(root) / "tasks"


def validate_task_id(task_id: str) -> str:
    if task_id == "":
        return task_id
    if not TASK_ID_PATTERN.fullmatch(task_id) or len(task_id) > 100 or task_id.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError("task ID must be a non-reserved name of at most 100 letters, numbers, dots, underscores, or hyphens")
    return task_id


def task_path(root: Path, task_id: str) -> Path:
    validate_task_id(task_id)
    return tasks_dir(root) / f"{task_id}.md"


def task_cycle_path(root: Path, task_id: str) -> Path:
    validate_task_id(task_id)
    return cycles_dir(root) / f"{task_id}.md"


def index_dir(root: Path) -> Path:
    return harness_dir(root) / "index"


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def today_cycle_path(root: Path, now: datetime | None = None) -> Path:
    date_text = (now or datetime.now()).strftime("%Y-%m-%d")
    return cycles_dir(root) / f"{date_text}.md"


def parse_date_text(date_text: str) -> str:
    """Validate and normalize a YYYY-MM-DD date string."""
    return datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m-%d")


def first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def markdown_list_items(text: str, limit: int = 8) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def file_status(path: Path) -> str:
    if path.exists():
        return "ok"
    return "missing"


def path_exists_text(path: Path) -> str:
    return "exists" if path.exists() else "missing"


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def print_text_or_json(data: Any, as_json: bool) -> None:
    if as_json:
        print(dump_json(data))
        return

    if isinstance(data, str):
        print(data)
        return

    print(dump_json(data))
