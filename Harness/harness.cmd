@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "HARNESS_INTERNAL_SCRIPT_ROOT=%~dp0"
set "HARNESS_INTERNAL_ARG_COUNT=0"

:collect_args
if "%~1"=="" goto run_harness
set /a HARNESS_INTERNAL_ARG_COUNT+=1 >nul
set "HARNESS_INTERNAL_ARG_%HARNESS_INTERNAL_ARG_COUNT%=%~1"
shift
goto collect_args

:run_harness
where pwsh.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HARNESS_INTERNAL_SCRIPT_ROOT%harness.ps1"
) else (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HARNESS_INTERNAL_SCRIPT_ROOT%harness.ps1"
)
exit /b %ERRORLEVEL%
