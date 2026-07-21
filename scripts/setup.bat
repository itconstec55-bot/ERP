@echo off
echo ======================================
echo   Accounting System Setup
echo ======================================
echo.

echo [1/7] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo Error: Make sure Python 3.10+ is installed
    pause
    exit /b 1
)

echo [2/7] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/7] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error installing dependencies
    pause
    exit /b 1
)

echo [4/7] Running migrations...
python manage.py migrate
if errorlevel 1 (
    echo Make sure PostgreSQL is running with database 'accounting_db'
    pause
    exit /b 1
)

echo [5/7] Setting up initial accounts...
python manage.py setup_accounts

echo [6/7] Creating admin user...
python manage.py createsuperuser

echo.
echo ======================================
echo   Setup Complete!
echo   To start: python manage.py runserver
echo   Then open: http://127.0.0.1:8000
echo ======================================
pause
