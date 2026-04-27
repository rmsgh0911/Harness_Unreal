@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_agents.ps1" %*
exit /b %ERRORLEVEL%
