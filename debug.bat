@echo off
rem Run MCQ Helper WITH a console window so any error is visible.
cd /d "%~dp0"
where python >nul 2>nul && (python "%~dp0mcq_helper.py") || (py -3 "%~dp0mcq_helper.py")
echo.
echo ---- last lines of mcq_helper.log ----
if exist mcq_helper.log powershell -NoProfile -Command "Get-Content -Tail 20 'mcq_helper.log'"
pause
