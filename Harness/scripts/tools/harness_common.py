"""Shared helpers for small Harness CLI tools."""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any


HARNESS_DIR_NAME = "Harness"
WORK_DIR_NAME = "work"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}
KOREAN_PARTICLE_SUFFIXES = (
    "으로부터", "에게서", "에서", "으로", "부터", "까지", "에게", "한테", "처럼", "보다",
    "과", "와", "을", "를", "은", "는", "이", "가", "에", "로", "의", "도", "만",
)


def readonly_git_env() -> dict[str, str]:
    """Inspect this checkout, never an index/repository selected by the caller's shell."""
    overrides = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_NAMESPACE",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX",
                 "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in overrides and not key.upper().startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
                       GIT_NO_REPLACE_OBJECTS="1", GIT_PAGER="cat", PYTHONDONTWRITEBYTECODE="1")
    return environment


def parse_git_status_z(output: str) -> list[dict]:
    """Parse porcelain v1 -z, including the second (original) rename/copy path."""
    fields = output.split("\0")
    if fields[-1] != "":
        raise ValueError("unterminated Git status output")
    fields.pop()
    entries = []
    index = 0
    while index < len(fields):
        field = fields[index]
        if len(field) < 4 or field[2] != " ":
            raise ValueError("malformed Git status entry")
        entry = {"status": field[:2], "path": field[3:]}
        index += 1
        if "R" in entry["status"] or "C" in entry["status"]:
            if index >= len(fields) or not fields[index]:
                raise ValueError("missing Git rename source")
            entry["original_path"] = fields[index]
            index += 1
        entries.append(entry)
    return entries


def launcher_command(arguments: str) -> str:
    """Return a runnable Harness launcher command for the current platform."""
    arguments = arguments.strip()
    if os.name == "nt":
        return f"& Harness\\harness.ps1 {arguments}".rstrip()
    return f"sh Harness/harness.sh {arguments}".rstrip()


def normalize_search_token(token: str) -> str:
    """Normalize a search token without applying broad stemming."""
    normalized = token.casefold()
    if re.fullmatch(r"[가-힣]+", normalized):
        for suffix in KOREAN_PARTICLE_SUFFIXES:
            if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
                return normalized[:-len(suffix)]
    return normalized


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


def is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    if junction and junction():
        return True
    # Path.is_junction is only available from Python 3.12. Earlier supported
    # Windows runtimes expose reparse-point attributes through lstat instead.
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    tag = getattr(info, "st_reparse_tag", None)
    if tag is not None:
        # Cloud-backed OneDrive files can also be reparse points without being
        # path-redirecting links; do not reject ordinary hydrated project files.
        return tag in {getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003),
                       getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C)}
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def require_owned_path(root: Path, path: Path) -> None:
    """Refuse writes/moves through links, including links to another owned record."""
    try:
        relative = path.absolute().relative_to(root.absolute())
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("record path escapes project root") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if is_link_or_junction(cursor):
            raise ValueError(f"record path contains a symlink or junction: {relative.as_posix()}")


def task_metadata_prefix(text: str) -> str:
    """Task fields belong to the leading metadata, never body examples or code."""
    boundary = re.search(r"^[ \t]*(?:#{2,}[ \t]|`{3,}|~{3,})", text, re.MULTILINE)
    return text[:boundary.start()] if boundary else text


def task_status(text: str) -> str:
    matches = re.findall(r"^[ \t]*-[ \t]*Status:[ \t]*([^\r\n]*)(?=\r?$)", task_metadata_prefix(text), re.IGNORECASE | re.MULTILINE)
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError("task record must contain exactly one non-empty Status field in leading metadata")
    return matches[0].strip().casefold()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def config_preflight(root: Path) -> dict:
    """Validate consumed configuration shapes before tools interpret truthy values."""
    schemas = {
        "Harness/config/project.json": {
            "template_mode": bool, "project_name": str, "uproject_file": str, "engine_version": str,
            "build": dict, "ci": dict, "build.engine_root": str, "build.editor_target_name": str,
            "build.game_target_name": str, "build.platform": str, "build.configuration": str,
            "ci.mode": str, "ci.allowed_modes": list,
        },
        "Harness/config/docs.json": {"doc_roots": list, "entry_points": list, "optional_external_roots": list,
                                     "read_policy": dict, "request_hints": dict, "request_hints.read": list, "request_hints.skip": list},
        "Harness/config/cycle_policy.json": {"default_max_cycles": int, "cycle_count_rules": dict,
                                            "cycle_count_rules.phrases": list, "stop_conditions": list},
        "Harness/config/agents.json": {"supported_workers": dict, "delegation_policy": dict, "subagent_roles": dict},
        "Harness/scripts/tools/tool_manifest.json": {"tools": list},
    }
    errors = []
    for relative, fields in schemas.items():
        path = root / relative
        if not path.exists():
            continue  # Presence is checked by doctor/readiness, not inferred here.
        try:
            data = load_json(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": relative, "error": f"cannot read valid UTF-8 JSON ({type(exc).__name__})"})
            continue
        if not isinstance(data, dict):
            errors.append({"path": relative, "error": "expected a JSON object"})
            continue
        for dotted, expected in fields.items():
            value = data
            for key in dotted.split("."):
                if not isinstance(value, dict) or key not in value:
                    break
                value = value[key]
            else:
                valid = type(value) is expected
                if valid and expected is list:
                    valid = all(isinstance(item, dict) if dotted == "tools" else isinstance(item, str) for item in value)
                if valid and dotted == "default_max_cycles":
                    valid = value >= 1
                if not valid:
                    errors.append({"path": relative, "error": f"invalid type/value for {dotted}; expected {expected.__name__}"})
        if relative.endswith("tool_manifest.json") and isinstance(data.get("tools"), list):
            for index, tool in enumerate(data["tools"]):
                if isinstance(tool, dict) and any(key in tool and not isinstance(tool[key], str) for key in ("name", "path", "purpose", "verify")):
                    errors.append({"path": relative, "error": f"tool entry {index + 1} requires string name/path/purpose/verify"})
        if relative.endswith("agents.json") and isinstance(data.get("supported_workers"), dict):
            for worker, entry in data["supported_workers"].items():
                instruction = entry.get("instruction_file") if isinstance(entry, dict) else None
                if not isinstance(instruction, str) or not instruction.strip():
                    errors.append({"path": relative, "error": f"worker {worker} requires a nonempty string instruction_file"})
                    continue
                normalized = instruction.replace("\\", "/")
                try:
                    if ":" in normalized or Path(normalized).is_absolute() or ".." in Path(normalized).parts:
                        raise ValueError("unsafe worker instruction path")
                    require_owned_path(root, root / normalized)
                except (OSError, ValueError, RuntimeError):
                    errors.append({"path": relative, "error": f"worker {worker} instruction_file must be an unlinked project-relative path"})
    return {"ok": not errors, "errors": errors}


def require_valid_config(root: Path) -> None:
    report = config_preflight(root)
    if not report["ok"]:
        raise ValueError("invalid Harness configuration: " + "; ".join(f"{item['path']}: {item['error']}" for item in report["errors"]))


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
