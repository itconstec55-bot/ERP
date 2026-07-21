@echo off
title Package Builder
color 0E

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo ======================================
echo   Building deployment package...
echo ======================================
echo.

set "OUTPUT_DIR=%PROJECT_DIR%dist"
set "PACKAGE_NAME=accounting_system"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo [1/3] Cleaning old files...
if exist "%OUTPUT_DIR%\%PACKAGE_NAME%.zip" del "%OUTPUT_DIR%\%PACKAGE_NAME%.zip"

echo [2/3] Creating package...

REM Use PowerShell to create a clean ZIP without temp files
powershell -Command ^
    "$src = '%PROJECT_DIR%';" ^
    "$dst = '%OUTPUT_DIR%\%PACKAGE_NAME%.zip';" ^
    "$exclude = @('.git','__pycache__','venv','env','deployment\backups','deployment\logs','deployment\updates','dist','*.pyc','*.pyo','db.sqlite3','staticfiles','media','error.html','error_page.html','parse_error.py','test_chart.py','test_dashboard.py','check_db.py','run_quick.py','run_quick2.py','run_accounts.py','run_migrate.py','run_types.py','run_setup.py','setup.bat');" ^
    "if (Test-Path $dst) { Remove-Item $dst };" ^
    "Compress-Archive -Path (" ^
    "  Get-ChildItem -Path $src -Recurse -File |" ^
    "    Where-Object { $ex = $false; foreach ($x in $exclude) { if ($_.Name -like $x -or $_.FullName -like \"*$x*\") { $ex = $true; break } }; -not $ex } |" ^
    "    ForEach-Object { $_.FullName }" ^
    ") -DestinationPath $dst -Force;" ^
    "Write-Host ('  Created: ' + $dst)"

echo [3/3] Package info:
echo.
for %%F in ("%OUTPUT_DIR%\%PACKAGE_NAME%.zip") do (
    set /a SIZE_KB=%%~zF/1024
    echo   File: %%~nxF
    echo   Size: !SIZE_KB! KB
)
echo.
echo ======================================
echo   Package ready: dist\accounting_system.zip
echo.
echo   On the target machine:
echo   1. Extract the ZIP
echo   2. Run: install.bat
echo   3. Run: start.bat
echo ======================================
echo.
pause
