@echo off
rem Launch MCQ Helper in the background (no console window).
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0mcq_helper.py"
    exit /b
)
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%~dp0mcq_helper.py"
    exit /b
)

echo Python was not found. Run setup.bat first.
pause
