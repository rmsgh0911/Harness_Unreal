"""Stable, thin command router for the portable Harness launchers."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, MutableMapping, Sequence

sys.dont_write_bytecode = True

from harness_common import find_project_root


COMMANDS = {
    "archive": "harness_archive.py",
    "artifacts": "harness_artifact_check.py",
    "close": "harness_work.py",
    "context": "harness_context.py",
    "cycle": "harness_cycle.py",
    "cycle-summary": "harness_cycle_summary.py",
    "diff-guard": "harness_diff_guard.py",
    "doctor": "harness_doctor.py",
    "docs-check": "harness_docs_check.py",
    "docs-index": "harness_docs_index.py",
    "field-check": "harness_field_check.py",
    "handoff": "harness_handoff.py",
    "init-plan": "harness_init_plan.py",
    "index-check": "harness_index_check.py",
    "iteration-status": "harness_iteration_status.py",
    "knowledge": "harness_knowledge.py",
    "local-gate": "harness_local_gate.py",
    "manifest": "harness_template_manifest.py",
    "memory": "harness_memory.py",
    "memory-review": "harness_memory_review.py",
    "migration-audit": "harness_migration_audit.py",
    "progress": "harness_progress_html.py",
    "progress-check": "harness_progress_check.py",
    "project-fill": "harness_project_fill.py",
    "python-check": "harness_python_check.py",
    "readiness": "harness_project_readiness.py",
    "release-check": "harness_release_check.py",
    "release-pack": "harness_release_pack.py",
    "scan": "harness_scan.py",
    "sensitive": "harness_sensitive_check.py",
    "state-check": "harness_state_check.py",
    "subagent": "harness_subagent.py",
    "tool-usage": "harness_tool_usage.py",
    "unreal-script": "harness_unreal_script.py",
    "update": "harness_update_plan.py",
    "unreal-risk": "harness_unreal_risk.py",
    "verify": "harness_verify_all.py",
}
LAUNCHER_COMMANDS = {"bootstrap"}
PRIMARY_COMMANDS = {
    "artifacts",
    "bootstrap",
    "close",
    "context",
    "cycle",
    "field-check",
    "handoff",
    "init-plan",
    "iteration-status",
    "local-gate",
    "memory-review",
    "project-fill",
    "readiness",
    "subagent",
    "update",
    "verify",
}
BRIDGE_COUNT = "HARNESS_INTERNAL_PY_ARG_COUNT"
BRIDGE_PREFIX = "HARNESS_INTERNAL_PY_ARG_"
BRIDGE_VALUE_PREFIX = "b64:"


def format_help() -> str:
    all_commands = {*COMMANDS, *LAUNCHER_COMMANDS}
    primary = "\n".join(f"  {name}" for name in sorted(PRIMARY_COMMANDS))
    supporting = "\n".join(f"  {name}" for name in sorted(all_commands - PRIMARY_COMMANDS))
    return (
        "Harness CLI\n"
        "Usage: harness <command> [arguments]\n\n"
        "Primary Commands:\n"
        f"{primary}\n\n"
        "Supporting Aliases:\n"
        f"{supporting}\n\n"
        "Arguments after the command are passed unchanged to the underlying tool.\n"
        "Direct python Harness/scripts/tools/*.py entry points remain supported."
    )


def build_invocation(argv: Sequence[str], executable: str | None = None) -> list[str] | None:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        return None
    command = argv[0].casefold()
    if command in LAUNCHER_COMMANDS:
        raise ValueError("bootstrap is handled by Harness/harness.ps1 or Harness/harness.sh, not direct Python")
    script_name = COMMANDS.get(command)
    if script_name is None:
        raise ValueError(f"unknown Harness command: {argv[0]}")
    script = Path(__file__).resolve().with_name(script_name)
    if not script.is_file():
        raise FileNotFoundError(f"Harness command implementation is missing: {script_name}")
    # Force UTF-8 for redirected output as well as interactive consoles. On
    # Windows, Python otherwise uses the active ANSI code page for pipes, which
    # can corrupt Korean requests when a packet is captured by another tool.
    return [executable or sys.executable, "-X", "utf8", "-B", str(script), *argv[1:]]


def consume_argument_bridge(environ: MutableMapping[str, str] = os.environ) -> list[str] | None:
    raw_count = environ.pop(BRIDGE_COUNT, None)
    if raw_count is None:
        return None
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise ValueError("invalid internal Harness argument bridge count") from exc
    if count < 0 or count > 4096:
        raise ValueError("invalid internal Harness argument bridge count")
    arguments: list[str] = []
    for index in range(1, count + 1):
        encoded = environ.pop(f"{BRIDGE_PREFIX}{index}", None)
        if encoded is None:
            raise ValueError(f"missing internal Harness argument bridge value: {index}")
        if not encoded.startswith(BRIDGE_VALUE_PREFIX):
            raise ValueError(f"invalid internal Harness argument bridge value: {index}")
        try:
            value = base64.b64decode(encoded[len(BRIDGE_VALUE_PREFIX) :], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"invalid internal Harness argument bridge value: {index}") from exc
        arguments.append(value)
    return arguments


def dispatch(
    argv: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    root: Path | None = None,
) -> int:
    invocation = build_invocation(argv)
    if invocation is None:
        print(format_help())
        return 0
    start = root if root is not None else Path(__file__).resolve().parent
    completed = runner(invocation, cwd=find_project_root(start), check=False)
    return int(completed.returncode)


def main() -> None:
    if sys.version_info < (3, 10):
        print("Harness requires Python 3.10 or newer.", file=sys.stderr)
        raise SystemExit(2)
    try:
        bridged = consume_argument_bridge()
        return_code = dispatch(bridged if bridged is not None else sys.argv[1:])
    except (FileNotFoundError, ValueError) as exc:
        print(f"Harness launcher error: {exc}", file=sys.stderr)
        print(format_help(), file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
