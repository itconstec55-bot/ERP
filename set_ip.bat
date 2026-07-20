@echo off
title Set Network IP
color 0B

echo.
echo ======================================
echo   Set Network IP Address
echo ======================================
echo.
echo Current network.conf:
type network.conf
echo.

set /p NEW_IP="Enter new IP address (e.g. 192.168.1.50): "

if "%NEW_IP%"=="" (
    echo No IP entered. Exiting.
    pause
    exit /b 1
)

echo.
echo Updating network.conf...

REM Update INTERNAL_IP
powershell -Command "(Get-Content 'network.conf') -replace '^INTERNAL_IP\s*=.*', 'INTERNAL_IP = %NEW_IP%' | Set-Content 'network.conf'"

REM Update EXTERNAL_IP
powershell -Command "(Get-Content 'network.conf') -replace '^EXTERNAL_IP\s*=.*', 'EXTERNAL_IP = %NEW_IP%' | Set-Content 'network.conf'"

echo Updating .env...

REM Update HOST_IP in .env
powershell -Command "(Get-Content '.env') -replace '^HOST_IP=.*', 'HOST_IP=%NEW_IP%' | Set-Content '.env'"

echo.
echo ======================================
echo   Done! Updated to: %NEW_IP%
echo ======================================
echo.
echo Updated network.conf:
type network.conf
echo.
echo Updated .env:
findstr "HOST_IP" .env
echo.
echo Restart the server to apply changes.
echo.
pause
