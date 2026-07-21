@echo off
title Accounting System - Server

REM ===== Check admin privileges (UAC) =====
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM ===== Read port from network.conf =====
set PORT=8001
for /f "tokens=2 delims== " %%a in ('findstr "PORT" network.conf') do set PORT=%%a
echo Opening port %PORT% in Windows Firewall...
netsh advfirewall firewall add rule name="Accounting_%PORT%" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Port opened (or already open).
) else (
    echo [!] Could not open port. Check permissions.
)

REM ===== Start on all interfaces =====
set DJANGO_DEBUG=true
cd /d "%~dp0"
echo.
echo Starting server on 0.0.0.0:%PORT% ...
echo Open browser: http://127.0.0.1:%PORT%/
echo Press Ctrl+C to stop
echo.
python manage.py runserver 0.0.0.0:%PORT%
pause
