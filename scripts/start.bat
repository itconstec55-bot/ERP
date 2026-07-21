@echo off
title Accounting System
color 0B

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo ======================================
echo   Accounting System - Starting...
echo ======================================
echo.

netstat -an | findstr ":8001 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   Server already running on port 8001
    echo   Open: http://127.0.0.1:8001
    echo.
    start http://127.0.0.1:8001
    pause
    exit /b 0
)

if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

echo   Server: http://127.0.0.1:8001
echo   Admin:  http://127.0.0.1:8001/admin/
echo   Stop:   Ctrl+C
echo.
start http://127.0.0.1:8001
%PYTHON% run_server.py
pause
