<#
.SYNOPSIS
    Migrates data from SQLite (local) to PostgreSQL (central)
.DESCRIPTION
    Run ONCE on the OLD device after PostgreSQL is set up and .env updated.
    Uses Django's dumpdata/loaddata to transfer all data.
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  SQLite -> PostgreSQL Data Migration" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "WARNING: Run this ONCE on the OLD device only!" -ForegroundColor Red
Write-Host "Make sure .env already points to PostgreSQL." -ForegroundColor Red
Write-Host ""

$ProjectPath = "D:\accounting_system"
Set-Location $ProjectPath

# Check .env points to PostgreSQL
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env not found!" -ForegroundColor Red
    exit 1
}
$envContent = Get-Content .env -Raw
if ($envContent -notmatch "postgresql://") {
    Write-Host "ERROR: .env doesn't point to PostgreSQL! Run update_env_postgresql.ps1 first." -ForegroundColor Red
    exit 1
}
Write-Host "OK: .env points to PostgreSQL" -ForegroundColor Green

# Activate venv
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "ERROR: venv not found! Run: python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
. venv\Scripts\activate.ps1

# Install psycopg2 if needed
Write-Host "Ensuring psycopg2 is installed..." -ForegroundColor Cyan
pip install psycopg2-binary -q

# Backup current SQLite (just in case)
Write-Host "`nBacking up SQLite database..." -ForegroundColor Cyan
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "db.sqlite3" "db.sqlite3.backup_$ts" -Force
Write-Host "  Backup: db.sqlite3.backup_$ts" -ForegroundColor Green

# Step 1: Dump data from SQLite (using current settings temporarily)
Write-Host "`nStep 1: Exporting data from SQLite..." -ForegroundColor Cyan

# Temporarily switch to SQLite for dump
$oldEnv = Get-Content .env -Raw
$tempEnv = $oldEnv -replace "postgresql://[^\s]+", "sqlite:///db.sqlite3"
$tempEnv | Set-Content .env -Encoding UTF8

$DumpFile = "migration_dump_$ts.json"
Write-Host "  Running dumpdata..." -ForegroundColor White
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e admin.LogEntry -e sessions.Session --indent 2 -o $DumpFile

if (-not (Test-Path $DumpFile)) {
    Write-Host "  ERROR: Dump failed!" -ForegroundColor Red
    $oldEnv | Set-Content .env -Encoding UTF8
    exit 1
}
$size = [math]::Round((Get-Item $DumpFile).Length / 1MB, 2)
Write-Host "  Dumped: $DumpFile ($size MB)" -ForegroundColor Green

# Step 2: Restore .env to PostgreSQL
$oldEnv | Set-Content .env -Encoding UTF8
Write-Host "`nStep 2: Switched back to PostgreSQL config" -ForegroundColor Cyan

# Step 3: Migrate schema on PostgreSQL
Write-Host "`nStep 3: Applying migrations on PostgreSQL..." -ForegroundColor Cyan
python manage.py migrate --run-syncdb

# Step 4: Load data into PostgreSQL
Write-Host "`nStep 4: Loading data into PostgreSQL..." -ForegroundColor Cyan
Write-Host "  This may take a while for large datasets..." -ForegroundColor Yellow
python manage.py loaddata $DumpFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n===============================================" -ForegroundColor Green
    Write-Host "  MIGRATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Data is now in PostgreSQL." -ForegroundColor White
    Write-Host "Dump file kept at: $DumpFile" -ForegroundColor White
    Write-Host "SQLite backup at: db.sqlite3.backup_$ts" -ForegroundColor White
    Write-Host ""
    Write-Host "Next: Run 'python run_seed.py' to ensure permissions are set" -ForegroundColor Cyan
} else {
    Write-Host "`n===============================================" -ForegroundColor Red
    Write-Host "  MIGRATION FAILED!" -ForegroundColor Red
    Write-Host "===============================================" -ForegroundColor Red
    Write-Host "Check errors above. Common issues:" -ForegroundColor Yellow
    Write-Host "  - Duplicate key conflicts (run seed first on clean DB)" -ForegroundColor White
    Write-Host "  - Foreign key violations (check dump order)" -ForegroundColor White
    Write-Host "  - Try: python manage.py flush --noinput then loaddata again" -ForegroundColor White
}