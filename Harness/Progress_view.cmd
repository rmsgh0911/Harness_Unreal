@echo off
rem Double-click launcher for the live Harness Progress viewer.
rem Starts a localhost static server so Progress_index.html can fetch the live
rem Progress.md (browsers block local fetch when the page is opened via file://).
rem %~dp0 is this Harness\ folder; its parent is the project root.
python "%~dp0scripts\tools\harness_progress_html.py" --serve --root "%~dp0.."
pause
