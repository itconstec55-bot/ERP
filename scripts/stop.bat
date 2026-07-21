@echo off
title Stop Accounting System
color 0C

echo.
echo ======================================
echo   Stopping Accounting System...
echo ======================================
echo.

REM -- Read port from network.conf --
set PORT=8001
for /f "tokens=2 delims== " %%a in ('findstr "PORT" network.conf') do set PORT=%%a

REM -- Find and kill Python processes on the port --
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo   Stopping process %%a...
    taskkill /F /PID %%a >nul 2>&1
)

REM -- Also kill any run_server.py processes --
taskkill /F /FI "WINDOWTITLE eq *run_server*" >nul 2>&1

REM -- Check result --
timeout /t 2 /nobreak >nul
netstat -an | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   System stopped successfully
) else (
    echo.
    echo   Warning: Server may not be fully stopped
)

echo.
pause
