@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

echo === Step 0: Migrate ===
python manage.py migrate
echo Migrate done: %ERRORLEVEL%

echo === Step 1: Setup Accounts ===
python manage.py setup_accounts
echo Setup accounts done: %ERRORLEVEL%

echo === Step 2: Seed Data ===
python manage.py seed_dummy_data --profile tiny --clear
echo Seed done: %ERRORLEVEL%

echo === Step 3: Start Server ===
python manage.py runserver 0.0.0.0:8000
