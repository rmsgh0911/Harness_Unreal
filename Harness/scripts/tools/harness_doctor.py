"""Check whether the Harness template structure is internally consistent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import find_project_root, harness_dir, load_json, read_text, print_text_or_json, rel


def check(condition: bool, message: str, severity: str = "error") -> dict:
    return {"ok": bool(condition), "severity": severity, "message": message}


def includes(text: str, needle: str) -> bool:
    return needle in text


def is_blank(value: object) -> bool:
    return value in (None, "", [], {})


def run_doctor(root: Path) -> dict:
    harness = harness_dir(root)
    results: list[dict] = []

    required_files = [
        root / "HARNESS.md",
        root / "AGENTS.md",
        harness / "README.md",
        harness / "state.md",
        harness / "next.md",
        harness / "config" / "project.json",
        harness / "config" / "agents.json",
        harness / "config" / "cycle_policy.json",
        harness / "config" / "docs.json",
        harness / "docs" / "README.md",
        harness / "scripts" / "unreal" / "verify_project.py",
        harness / "scripts" / "unreal" / "create_level.py",
        harness / "scripts" / "build" / "build_verify.ps1",
        harness / "scripts" / "build" / "build_verify.cmd",
        harness / "scripts" / "tools" / "tool_manifest.json",
        harness / "scripts" / "tools" / "harness_common.py",
    ]
    for path in required_files:
        results.append(check(path.exists(), f"required file exists: {path.relative_to(root).as_posix()}"))

    ag_text = read_text(root / "AGENTS.md")
    cl_text = read_text(root / "CLAUDE.md")
    harness_text = read_text(root / "HARNESS.md")
    results.append(check(includes(ag_text, "HARNESS.md"), "AGENTS.md routes agents to HARNESS.md"))
    if (root / "CLAUDE.md").exists():
        results.append(check(includes(cl_text, "HARNESS.md"), "CLAUDE.md routes Claude Code to HARNESS.md"))
    results.append(check(includes(harness_text, "최대 N사이클"), "HARNESS.md explains max-cycle requests"))
    results.append(check(includes(harness_text, "도구 추가"), "HARNESS.md explains agent-added tools"))
    results.append(check(includes(harness_text, "Harness/docs"), "HARNESS.md explains default project document root"))
    results.append(check(includes(harness_text, "docs.json"), "HARNESS.md explains docs.json policy"))

    json_paths = [
        harness / "config" / "project.json",
        harness / "config" / "agents.json",
        harness / "config" / "cycle_policy.json",
        harness / "config" / "docs.json",
        harness / "scripts" / "tools" / "tool_manifest.json",
    ]
    for path in json_paths:
        data = None
        try:
            data = load_json(path, None)
            ok = isinstance(data, dict)
        except Exception as exc:  # noqa: BLE001
            ok = False
            data = str(exc)
        results.append(check(ok, f"json parses: {path.relative_to(root).as_posix()}"))
        if path.name == "cycle_policy.json" and isinstance(data, dict):
            results.append(check("cycle_count_rules" in data, "cycle_policy.json has cycle_count_rules"))
            results.append(check("tool_policy" in data, "cycle_policy.json has tool_policy"))
        if path.name == "tool_manifest.json" and isinstance(data, dict):
            tools = data.get("tools", [])
            results.append(check(isinstance(tools, list), "tool_manifest.json has tools list"))
            names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
            results.append(check(len(names) == len(set(names)), "tool_manifest.json tool names are unique"))
            declared_paths = {tool.get("path") for tool in tools if isinstance(tool, dict)}
            for index, tool in enumerate(tools, start=1):
                name = tool.get("name", f"tool #{index}") if isinstance(tool, dict) else f"tool #{index}"
                results.append(check(isinstance(tool, dict), f"manifest entry is object: {name}"))
                if not isinstance(tool, dict):
                    continue
                declared_path = tool.get("path", "")
                tool_path = root / declared_path
                results.append(check(bool(tool.get("name")), f"manifest tool has name: {name}"))
                results.append(check(bool(tool.get("purpose")), f"manifest tool has purpose: {name}"))
                results.append(check(str(declared_path).startswith("Harness/scripts/tools/"), f"manifest tool stays under tools: {name}"))
                results.append(check(tool_path.exists(), f"manifest tool path exists: {declared_path or name}"))
                results.append(check("writes_files" in tool, f"manifest tool declares writes_files: {name}"))
                results.append(check(tool.get("safe_by_default") is True, f"manifest tool is safe by default: {name}"))
                results.append(check(bool(tool.get("verify")), f"manifest tool has verify command: {name}"))
                if tool.get("verify"):
                    results.append(
                        check(
                            str(declared_path) in str(tool.get("verify")),
                            f"manifest verify command references tool path: {name}",
                            "warning",
                        )
                    )

            tool_scripts = sorted((harness / "scripts" / "tools").glob("*.py"))
            for script in tool_scripts:
                script_rel = rel(script, root)
                if script.name == "harness_common.py":
                    continue
                results.append(
                    check(
                        script_rel in declared_paths,
                        f"tool script is listed in manifest: {script_rel}",
                        "warning",
                    )
                )

    project = load_json(harness / "config" / "project.json", {}) or {}
    if isinstance(project, dict):
        project_fields = ["project_name", "uproject_file", "engine_version"]
        blank_project_fields = [field for field in project_fields if is_blank(project.get(field))]
        build = project.get("build", {}) if isinstance(project.get("build", {}), dict) else {}
        blank_build_fields = [field for field in ["engine_root", "editor_target_name"] if is_blank(build.get(field))]
        has_real_uproject = bool(list(root.glob("*.uproject")))
        if has_real_uproject:
            for field in blank_project_fields:
                results.append(check(False, f"project.json field is configured: {field}", "warning"))
            for field in blank_build_fields:
                results.append(check(False, f"project.json build field is configured: build.{field}", "warning"))
        else:
            results.append(
                check(
                    True,
                    "project.json may stay blank in the standalone template repository",
                    "warning",
                )
            )

    generated_python_files = [
        *sorted((harness / "scripts").rglob("__pycache__")),
        *sorted((harness / "scripts").rglob("*.pyc")),
    ]
    results.append(
        check(
            not generated_python_files,
            "Harness scripts contain no generated Python cache files",
            "warning",
        )
    )

    cycles_dir = harness / "cycles"
    tools_dir = harness / "scripts" / "tools"
    unreal_dir = harness / "scripts" / "unreal"
    build_dir = harness / "scripts" / "build"
    results.extend(
        [
            check(cycles_dir.is_dir(), "cycles directory exists"),
            check(unreal_dir.is_dir(), "unreal scripts directory exists"),
            check(build_dir.is_dir(), "build scripts directory exists"),
            check(tools_dir.is_dir(), "tools directory exists"),
        ]
    )

    errors = [item for item in results if not item["ok"] and item["severity"] == "error"]
    warnings = [item for item in results if not item["ok"] and item["severity"] == "warning"]
    return {
        "root": str(root),
        "ok": not errors,
        "summary": {
            "checks": len(results),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "checks": results,
    }


def format_text(result: dict) -> str:
    lines = [
        "Harness Doctor",
        f"- Root: {result['root']}",
        f"- Status: {'ok' if result['ok'] else 'needs attention'}",
        f"- Checks: {result['summary']['checks']}",
        f"- Errors: {result['summary']['errors']}",
        f"- Warnings: {result['summary']['warnings']}",
        "",
        "Details:",
    ]
    for item in result["checks"]:
        mark = "OK" if item["ok"] else item["severity"].upper()
        lines.append(f"- [{mark}] {item['message']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Harness structure and policy files.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    result = run_doctor(root)
    print_text_or_json(result if args.json else format_text(result), args.json)
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
