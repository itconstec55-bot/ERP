@echo off
title Accounting System - Service Mode
color 0B

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo ======================================
echo   Accounting System - Service Mode
echo   (Monitoring + Backup + Auto-update)
echo ======================================
echo.

REM -- Check for venv --
if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

REM -- Start service --
echo   Services:
echo     - Main server
echo     - Health monitoring (auto-restart)
echo     - Backup (every 2 hours)
echo     - Silent update (every hour)
echo.
echo   Press Ctrl+C to stop
echo.

%PYTHON% deployment\service.py
pause
