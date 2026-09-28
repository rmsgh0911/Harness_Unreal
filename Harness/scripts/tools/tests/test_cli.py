"""Regression tests for the stable Harness CLI router."""

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from _harness_test_base import *  # noqa: F401,F403

from harness_cli import COMMANDS, PRIMARY_COMMANDS, build_invocation, consume_argument_bridge, dispatch, format_help
from harness_python_check import run_version


class CliTests(HarnessBaseTestCase):
    def test_help_lists_the_small_public_surface(self) -> None:
        help_text = format_help()
        self.assertIn("context", help_text)
        self.assertIn("verify", help_text)
        self.assertIn("local-gate", help_text)
        self.assertIn("close", help_text)
        self.assertIn("artifacts", help_text)
        self.assertIn("subagent", help_text)
        self.assertIn("bootstrap", help_text)
        self.assertIn("project-fill", help_text)
        self.assertIn("init-plan", help_text)
        self.assertIn("field-check", help_text)
        self.assertIn("iteration-status", help_text)
        self.assertIn("memory-review", help_text)
        self.assertIn("manifest", help_text)
        self.assertIn("migration-audit", help_text)
        self.assertIn("progress", help_text)

    def test_every_router_tool_is_registered_even_with_project_extensions(self) -> None:
        tools_dir = Path(__file__).resolve().parents[1]
        manifest = json.loads((tools_dir / "tool_manifest.json").read_text(encoding="utf-8"))
        required = {f"Harness/scripts/tools/{name}" for name in {*COMMANDS.values(), "harness_cli.py"}}
        for tools in [manifest["tools"], [*manifest["tools"], {"path": "Harness/scripts/tools/project_custom.py"}]]:
            registered = {tool["path"] for tool in tools}
            self.assertTrue(required.issubset(registered), required - registered)
        self.assertTrue(PRIMARY_COMMANDS.issubset({*COMMANDS, "bootstrap"}))

    def test_arguments_with_spaces_and_korean_are_forwarded_exactly(self) -> None:
        request = "한글 경로와 공백 유지"
        invocation = build_invocation(["context", "--request", request], executable="python-test")

        self.assertEqual("python-test", invocation[0])
        self.assertEqual(["--request", request], invocation[-2:])

    def test_internal_argument_bridge_preserves_quotes_metacharacters_and_empty_values(self) -> None:
        values = ['&echo probe %PATH% "quoted"', "", "한글"]
        environment = {"HARNESS_INTERNAL_PY_ARG_COUNT": str(len(values))}
        environment.update(
            {
                f"HARNESS_INTERNAL_PY_ARG_{index}": "b64:"
                + base64.b64encode(value.encode("utf-8")).decode("ascii")
                for index, value in enumerate(values, start=1)
            }
        )

        self.assertEqual(values, consume_argument_bridge(environment))
        self.assertEqual({}, environment)

    def test_subagent_arguments_are_forwarded_exactly(self) -> None:
        request = "현재 상황과 커밋 범위"
        invocation = build_invocation(
            ["subagent", "--role", "current-status", "--request", request],
            executable="python-test",
        )

        self.assertTrue(invocation[4].endswith("harness_subagent.py"))
        self.assertEqual(["--role", "current-status", "--request", request], invocation[5:])

    def test_child_invocation_forces_utf8_mode(self) -> None:
        invocation = build_invocation(["context", "--request", "한글"], executable="python-test")

        self.assertEqual(["python-test", "-X", "utf8", "-B"], invocation[:4])

    def test_dispatch_uses_argument_array_and_propagates_exit_code(self) -> None:
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 7)

        return_code = dispatch(["verify", "--skip-tool-tests"], runner=fake_runner, root=self.root)

        self.assertEqual(7, return_code)
        self.assertEqual(["-X", "utf8", "-B"], calls[0][0][1:4])
        self.assertTrue(calls[0][0][4].endswith("harness_verify_all.py"))
        self.assertEqual("--skip-tool-tests", calls[0][0][5])
        self.assertFalse(calls[0][1]["check"])

    def test_python_diagnostic_disables_install_manager_downloads(self) -> None:
        completed = subprocess.CompletedProcess(["py", "-3", "--version"], 0, "Python 3.12.0\n", "")
        with patch("harness_python_check.shutil.which", return_value="py"), patch(
            "harness_python_check.subprocess.run", return_value=completed
        ) as runner:
            report = run_version(["py", "-3"])

        self.assertTrue(report["ok"])
        self.assertEqual("0", runner.call_args.kwargs["env"]["PYTHON_MANAGER_AUTOMATIC_INSTALL"])

    def test_cli_process_uses_install_root_outside_current_directory(self) -> None:
        cli = Path(__file__).resolve().parents[1] / "harness_cli.py"
        install_root = Path(__file__).resolve().parents[4]

        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(cli),
                "context",
                "--request",
                "outside cwd",
                "--no-memory",
                "--json",
            ],
            cwd=self.root,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        payload = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(str(install_root), payload["root"])

    def test_unknown_command_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown Harness command"):
            build_invocation(["does-not-exist"])

    @unittest.skipUnless(os.name == "nt", "Windows batch launcher regression")
    def test_windows_cmd_launcher_preserves_unicode_arguments(self) -> None:
        wrapper = Path(__file__).resolve().parents[3] / "harness.cmd"
        marker = "한글 경로 100% & safe ! ^"

        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(wrapper), marker],
            cwd=wrapper.parent.parent,
            capture_output=True,
            check=False,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn(marker, completed.stderr.decode("utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows native bootstrap regression")
    def test_windows_bootstrap_help_does_not_require_python(self) -> None:
        wrapper = Path(__file__).resolve().parents[3] / "harness.cmd"
        environment = {**os.environ, "HARNESS_PYTHON": str(self.root / "missing-python.exe")}

        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(wrapper), "bootstrap", "--help"],
            cwd=wrapper.parent.parent,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        self.assertIn("Normal Harness commands never trigger", completed.stdout.decode("utf-8"))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is unavailable")
    def test_windows_powershell_fallback_parses_bootstrap_without_python(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        environment = {
            **os.environ,
            "HARNESS_INTERNAL_ARG_COUNT": "2",
            "HARNESS_INTERNAL_ARG_1": "bootstrap",
            "HARNESS_INTERNAL_ARG_2": "--help",
            "HARNESS_PYTHON": str(self.root / "missing-python.exe"),
        }

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(harness / "harness.ps1"),
            ],
            cwd=harness.parent,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        self.assertIn("Harness Python Bootstrap", completed.stdout.decode("utf-8"))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is unavailable")
    def test_windows_powershell_launcher_preserves_free_form_arguments(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        harness_script = str(harness / "harness.ps1").replace("'", "''")
        requests = ['&echo.HARNESS_INJECTION_PROBE %PATH% "quoted"', ""]
        for request in requests:
            with self.subTest(request=request):
                encoded_request = base64.b64encode(request.encode("utf-8")).decode("ascii")
                command = (
                    f"$request = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_request}')); "
                    f"& '{harness_script}' context --request $request --no-memory --json; exit $LASTEXITCODE"
                )

                completed = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoLogo",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        command,
                    ],
                    cwd=harness.parent,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
                payload = json.loads(completed.stdout.decode("utf-8-sig"))
                self.assertEqual(request, payload["cycle_policy"]["request_eval"]["request"])

    @unittest.skipUnless(os.name == "nt", "Windows managed-runtime regression")
    def test_windows_launcher_uses_managed_runtime_marker(self) -> None:
        wrapper = Path(__file__).resolve().parents[3] / "harness.cmd"
        runtime = self.root / "managed-runtime"
        fake_python = runtime / "python/fake/python.cmd"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text(
            '@echo off\r\nif "%~1"=="-c" exit /b 0\r\necho MANAGED_PYTHON %*\r\n'
            'echo MANAGED_ARG_1 %HARNESS_INTERNAL_PY_ARG_1%\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
        (runtime / "python.path").write_text(f"{fake_python}\n", encoding="utf-8")
        environment = dict(os.environ)
        environment.pop("HARNESS_PYTHON", None)
        environment["HARNESS_RUNTIME_ROOT"] = str(runtime)

        commands = [
            ["context", "--request", "managed runtime"],
            ["local-gate", "--help"],
            ["readiness", "--help"],
            ["manifest", "--help"],
        ]
        for arguments in commands:
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    ["cmd.exe", "/d", "/c", str(wrapper), *arguments],
                    cwd=wrapper.parent.parent,
                    env=environment,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
                output = completed.stdout.decode("utf-8")
                self.assertIn("MANAGED_PYTHON -X utf8 -B", output)
                encoded_command = "b64:" + base64.b64encode(arguments[0].encode("utf-8")).decode("ascii")
                self.assertIn(f"MANAGED_ARG_1 {encoded_command}", output)

    @unittest.skipUnless(os.name == "nt", "Windows managed-runtime bootstrap regression")
    def test_windows_bootstrap_accepts_supplied_uv_without_system_python(self) -> None:
        wrapper = Path(__file__).resolve().parents[3] / "harness.cmd"
        runtime = self.root / "bootstrap-runtime"
        fake_python = runtime / "python/fake/python.cmd"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text(
            '@echo off\r\nif "%~1"=="-c" exit /b 0\r\necho Python 3.12.fake\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
        fake_uv = self.root / "fake-uv.cmd"
        cache = self.root / "offline cache"
        cache_sentinel = self.root / "cache-used.txt"
        fake_uv.write_text(
            "@echo off\r\n"
            'if "%~1"=="--version" (\r\n'
            "  echo uv 0.12.18\r\n"
            "  exit /b 0\r\n"
            ")\r\n"
            'if "%~1"=="python" if "%~2"=="install" (\r\n'
            '  >"%HARNESS_CACHE_SENTINEL%" echo %UV_CACHE_DIR%\r\n'
            "  exit /b 0\r\n"
            ")\r\n"
            'if "%~1"=="python" if "%~2"=="find" (\r\n'
            f"  echo {fake_python}\r\n"
            "  exit /b 0\r\n"
            ")\r\n"
            "exit /b 9\r\n",
            encoding="utf-8",
        )
        environment = {
            **os.environ,
            "HARNESS_PYTHON": str(self.root / "missing-python.exe"),
            "HARNESS_RUNTIME_ROOT": str(runtime),
            "HARNESS_UV": str(fake_uv),
            "HARNESS_UV_CACHE_DIR": str(cache),
            "HARNESS_CACHE_SENTINEL": str(cache_sentinel),
        }

        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(wrapper), "bootstrap"],
            cwd=wrapper.parent.parent,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(str(fake_python), (runtime / "python.path").read_text(encoding="utf-8").strip())
        self.assertEqual(str(cache), cache_sentinel.read_text(encoding="utf-8").strip())
        self.assertIn("Harness managed Python is ready", completed.stdout.decode("utf-8"))

        environment["HARNESS_UV"] = str(self.root / "missing-uv.exe")
        reused = subprocess.run(
            ["cmd.exe", "/d", "/c", str(wrapper), "bootstrap"],
            cwd=wrapper.parent.parent,
            env=environment,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, reused.returncode, reused.stderr.decode("utf-8", errors="replace"))
        self.assertIn("already ready", reused.stdout.decode("utf-8"))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is unavailable")
    def test_windows_probe_disables_python_manager_automatic_install(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        sentinel = self.root / "automatic-install-attempted"
        (fake_bin / "py.cmd").write_text(
            "@echo off\r\n"
            'if not "%PYTHON_MANAGER_AUTOMATIC_INSTALL%"=="0" echo attempted>"%HARNESS_NETWORK_SENTINEL%"\r\n'
            "exit /b 3\r\n",
            encoding="utf-8",
        )
        environment = {
            **os.environ,
            "HARNESS_RUNTIME_ROOT": str(self.root / "missing-runtime"),
            "HARNESS_NETWORK_SENTINEL": str(sentinel),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        environment.pop("HARNESS_PYTHON", None)

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(harness / "harness.ps1"),
                "--help",
            ],
            cwd=harness.parent,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        self.assertFalse(sentinel.exists())

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is unavailable")
    def test_windows_launcher_rejects_managed_runtime_junction_escape(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        runtime = self.root / "junction-runtime"
        runtime.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = self.root / "escaped-python-ran"
        fake_python = outside / "python.cmd"
        fake_python.write_text(
            f'@echo off\r\necho ran>"{sentinel}"\r\nexit /b 0\r\n',
            encoding="utf-8",
        )
        junction = runtime / "python"
        linked = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
            check=False,
        )
        if linked.returncode != 0:
            self.skipTest("junction creation is unavailable")
        try:
            (runtime / "python.path").write_text(f"{junction / 'python.cmd'}\n", encoding="utf-8")
            environment = {**os.environ, "HARNESS_RUNTIME_ROOT": str(runtime)}
            environment.pop("HARNESS_PYTHON", None)

            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(harness / "harness.ps1"),
                    "--help",
                ],
                cwd=harness.parent,
                env=environment,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
            self.assertFalse(sentinel.exists())
        finally:
            junction.rmdir()

    @unittest.skipUnless(shutil.which("bash"), "bash is unavailable")
    def test_posix_launchers_pass_shell_syntax_validation(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        for script in ["harness.sh", "bootstrap.sh"]:
            completed = subprocess.run(
                ["bash", "-n", f"Harness/{script}"],
                cwd=harness.parent,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))

    @unittest.skipUnless(os.name != "nt" and shutil.which("sh"), "POSIX shell regression")
    def test_posix_invalid_explicit_uv_never_falls_back_to_network(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        runtime = self.root / "bootstrap-runtime"
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        network_sentinel = self.root / "network-attempted"
        fake_curl = fake_bin / "curl"
        fake_curl.write_text(
            '#!/usr/bin/env sh\ntouch "$HARNESS_NETWORK_SENTINEL"\nexit 91\n',
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)
        environment = {
            **os.environ,
            "HARNESS_RUNTIME_ROOT": str(runtime),
            "HARNESS_UV": str(self.root / "missing-uv"),
            "HARNESS_NETWORK_SENTINEL": str(network_sentinel),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        }

        completed = subprocess.run(
            ["sh", str(harness / "bootstrap.sh")],
            cwd=harness.parent,
            env=environment,
            capture_output=True,
            check=False,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("no network fallback was attempted", completed.stderr.decode("utf-8"))
        self.assertFalse(network_sentinel.exists())

    @unittest.skipUnless(os.name != "nt" and shutil.which("sh"), "POSIX shell regression")
    def test_posix_bootstrap_roundtrip_reuses_runtime_and_rejects_marker_escape(self) -> None:
        harness = Path(__file__).resolve().parents[3]
        runtime = self.root / "runtime with spaces"
        fake_python = runtime / "python/fake/bin/python3.12"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text(
            "#!/usr/bin/env sh\n"
            'if [ "${1:-}" = "-c" ]; then exit 0; fi\n'
            'echo "MANAGED_PYTHON $*"\n',
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        fake_uv = self.root / "fake uv"
        fake_uv.write_text(
            "#!/usr/bin/env sh\n"
            'if [ "${1:-}" = "--version" ]; then echo "uv 0.12.18"; exit 0; fi\n'
            'if [ "${1:-}:${2:-}" = "python:install" ]; then printf "%s" "$UV_CACHE_DIR" > "$HARNESS_CACHE_SENTINEL"; exit 0; fi\n'
            'if [ "${1:-}:${2:-}" = "python:find" ]; then printf "%s\\n" "$HARNESS_FAKE_PYTHON"; exit 0; fi\n'
            "exit 9\n",
            encoding="utf-8",
        )
        fake_uv.chmod(0o755)
        cache = self.root / "offline cache"
        cache_sentinel = self.root / "cache-used"
        environment = {
            **os.environ,
            "HARNESS_RUNTIME_ROOT": str(runtime),
            "HARNESS_UV": str(fake_uv),
            "HARNESS_UV_CACHE_DIR": str(cache),
            "HARNESS_CACHE_SENTINEL": str(cache_sentinel),
            "HARNESS_FAKE_PYTHON": str(fake_python),
        }

        completed = subprocess.run(
            ["sh", str(harness / "harness.sh"), "bootstrap"],
            cwd=harness.parent,
            env=environment,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(str(fake_python.resolve()), (runtime / "python.path").read_text(encoding="utf-8").strip())
        self.assertEqual(str(cache), cache_sentinel.read_text(encoding="utf-8"))

        environment["HARNESS_UV"] = str(self.root / "missing uv")
        reused = subprocess.run(
            ["sh", str(harness / "harness.sh"), "bootstrap"],
            cwd=harness.parent,
            env=environment,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, reused.returncode, reused.stderr.decode("utf-8", errors="replace"))
        self.assertIn("already ready", reused.stdout.decode("utf-8"))

        escaped_runtime = self.root / "escaped-runtime"
        escaped_runtime.mkdir()
        evil = self.root / "evil/python"
        evil.parent.mkdir()
        escape_sentinel = self.root / "escaped-python-ran"
        evil.write_text(
            f'#!/usr/bin/env sh\ntouch "{escape_sentinel}"\nexit 0\n',
            encoding="utf-8",
        )
        evil.chmod(0o755)
        (escaped_runtime / "python.path").write_text(
            f"{escaped_runtime}/../evil/python\n",
            encoding="utf-8",
        )
        escaped_environment = {
            **os.environ,
            "HARNESS_RUNTIME_ROOT": str(escaped_runtime),
        }
        subprocess.run(
            ["sh", str(harness / "harness.sh"), "--help"],
            cwd=harness.parent,
            env=escaped_environment,
            capture_output=True,
            check=False,
        )
        self.assertFalse(escape_sentinel.exists())

        unresolved = self.root / "not-created/../runtime"
        unresolved_environment = {
            **os.environ,
            "HARNESS_RUNTIME_ROOT": str(unresolved),
            "HARNESS_UV": str(fake_uv),
        }
        rejected = subprocess.run(
            ["sh", str(harness / "harness.sh"), "bootstrap"],
            cwd=harness.parent,
            env=unresolved_environment,
            capture_output=True,
            check=False,
        )
        self.assertEqual(2, rejected.returncode)
        self.assertIn("cannot contain '..'", rejected.stderr.decode("utf-8"))
