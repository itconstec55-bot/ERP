@echo off
title Accounting System Installer v1.0
color 0A

echo.
echo ======================================
echo   Accounting System Installer v1.0
echo ======================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "VENV_PY=%PROJECT_DIR%venv\Scripts\python.exe"
set "VENV_PIP=%PROJECT_DIR%venv\Scripts\pip.exe"

echo [1/8] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo !! Python is not installed !!
    echo Opening download page...
    echo.
    start https://www.python.org/downloads/
    echo.
    echo Install Python 3.10+ and check "Add Python to PATH"
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Found: %PYVER%

echo.
echo [2/8] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing pip...
    python -m ensurepip --default-pip
    python -m pip install --upgrade pip
)

echo.
echo [3/8] Creating virtual environment...
if not exist "%VENV_PY%" (
    python -m venv venv
    if not exist "%VENV_PY%" (
        echo   ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo   Virtual environment created
) else (
    echo   Virtual environment already exists
)

echo.
echo [4/8] Installing dependencies...
"%VENV_PIP%" install --upgrade pip
"%VENV_PIP%" install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo   Dependencies installed

echo.
echo [5/8] Generating secret key and setting up .env...
set "DJANGO_SETTINGS_MODULE=accounting_system.settings"
set "DJANGO_DEBUG=True"
for /f %%k in ('"%VENV_PY%" -c "import secrets; print(secrets.token_urlsafe(50))"') do set "NEW_KEY=%%k"
set "DJANGO_SECRET_KEY=%NEW_KEY%"

if not exist ".env" (
    echo DJANGO_SECRET_KEY=%NEW_KEY%> .env
    echo DJANGO_DEBUG=True>> .env
    echo DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost>> .env
    echo   .env file created
) else (
    echo   .env file already exists
)

echo.
echo [6/8] Running migrations...
"%VENV_PY%" manage.py migrate --no-input
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Database setup failed!
    pause
    exit /b 1
)
echo   Database ready

echo.
echo [7/8] Setting up chart of accounts...
"%VENV_PY%" manage.py setup_accounts

echo.
echo [8/8] Creating admin user...
"%VENV_PY%" manage.py create_admin --username admin --password admin123

echo.
echo   Collecting static files...
"%VENV_PY%" manage.py collectstatic --no-input

echo.
echo ======================================
echo   Installation Complete!
echo ======================================
echo.
echo   To start: start.bat
echo   Open browser: http://127.0.0.1:PORT
echo   Admin panel: http://127.0.0.1:PORT/admin/
echo   User: admin / admin123
echo   (PORT is defined in network.conf)
echo.
pause
