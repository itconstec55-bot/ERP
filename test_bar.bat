@echo off
cd /d "%~dp0"
python -m pytest tests/bar_test.py -v
pause
