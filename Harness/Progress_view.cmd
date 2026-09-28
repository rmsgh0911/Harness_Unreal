@echo off
rem Double-click launcher for the live Harness Progress viewer.
rem Starts a localhost static server so Progress_index.html can fetch the live
rem Progress.md (browsers block local fetch when the page is opened via file://).
rem %~dp0 is this Harness\ folder; its parent is the project root.
call "%~dp0harness.cmd" progress --serve --root "%~dp0.."
set "HARNESS_VIEW_EXIT=%ERRORLEVEL%"
if not "%HARNESS_VIEW_EXIT%"=="0" pause
exit /b %HARNESS_VIEW_EXIT%
