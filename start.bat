@echo off
rem Launch MCQ Helper in the background (no console window).
cd /d "%~dp0"
start "" pythonw mcq_helper.py
