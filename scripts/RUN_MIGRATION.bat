@echo off
REM =====================================================================
REM  Accounting System - Full Migration to New Machine (PostgreSQL)
REM  Quick start guide - run steps in order
REM =====================================================================

echo.
echo ================================================================
echo  ACCOUNTING SYSTEM - MIGRATION TO NEW MACHINE (PostgreSQL)
echo ================================================================
echo.

echo Step 1: Create full backup (on old machine)
echo --------------------------------------------------------------
echo File: create_full_backup.ps1
echo Output: D:\accounting_system_backups\accounting_system_FULL_*.zip
echo.
powershell -ExecutionPolicy Bypass -File "D:\accounting_system\create_full_backup.ps1"
if errorlevel 1 (
    echo [FAILED] Step 1
    pause
    exit /b 1
)
echo [OK] Step 1 complete
echo.

echo Step 2: Setup PostgreSQL as central database
echo --------------------------------------------------------------
echo On the machine that will host the database:
echo File: setup_postgresql_server.ps1
echo ** Run as Administrator **
echo.
echo Run on database machine:
echo   powershell -ExecutionPolicy Bypass -File setup_postgresql_server.ps1
echo.
echo It will print connection info - save it!
echo.
pause

echo Step 3: Update connection on old machine
echo --------------------------------------------------------------
echo File: update_env_postgresql.ps1
echo ** Edit variables at top of file: **
echo    $DB_SERVER_IP = "DATABASE_MACHINE_IP"
echo    $DB_PASSWORD = "password_from_step_2"
echo.
echo Run:
echo   powershell -ExecutionPolicy Bypass -File update_env_postgresql.ps1
echo.
pause

echo Step 4: Migrate data SQLite -> PostgreSQL (once on old machine)
echo --------------------------------------------------------------
echo File: migrate_sqlite_to_postgresql.ps1
echo ** Run on old machine only (has current data) **
echo.
echo Run:
echo   powershell -ExecutionPolicy Bypass -File migrate_sqlite_to_postgresql.ps1
echo.
pause

echo Step 5: Prepare new machine
echo --------------------------------------------------------------
echo 1. Copy zip to new machine
echo 2. Extract to D:\accounting_system
echo 3. Run these commands:
echo.
echo   cd D:\accounting_system
echo   python -m venv venv
echo   venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install psycopg2-binary
echo   python manage.py migrate
echo   python manage.py collectstatic
echo.
echo 4. Edit update_env_postgresql.ps1 with connection info
echo 5. Run:
echo   powershell -ExecutionPolicy Bypass -File update_env_postgresql.ps1
echo.
pause

echo Step 6: Seed data (on one machine only)
echo --------------------------------------------------------------
echo python run_seed.py
echo.
pause

echo Step 7: Start
echo --------------------------------------------------------------
echo On both machines:
echo   python run_waitress.py
echo.
echo Or:
echo   start_production.bat
echo.

echo ================================================================
echo  DONE! Application runs on both machines with one database
echo ================================================================
echo.
pause
