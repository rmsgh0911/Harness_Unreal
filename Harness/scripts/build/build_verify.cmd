@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_verify.ps1" %*
exit /b %ERRORLEVEL%
