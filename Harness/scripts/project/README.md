# Project Tools

Put project-specific CPython, PowerShell, Node, or other utilities here. Keep reusable Harness framework tools in `Harness/scripts/tools/`, and keep scripts that import `unreal` in `Harness/scripts/unreal/` so they use the Unreal wrapper.

Register project utilities in `project_tool_manifest.json`. Harness updates preserve this directory and never merge its manifest into the core tool registry automatically.
