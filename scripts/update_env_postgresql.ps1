<#
.SYNOPSIS
    Updates .env file to connect to PostgreSQL central database
.DESCRIPTION
    Run on EACH application device (old and new) after PostgreSQL server is set up.
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Update .env for PostgreSQL Connection" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# CONFIGURATION - غيّر هذه القيم
# ============================================================
$DB_SERVER_IP   = "192.168.1.100"   # IP جهاز قاعدة البيانات (الجهاز اللي نصب عليه PostgreSQL)
$DB_PORT        = 5432
$DB_NAME        = "accounting_db"
$DB_USER        = "accounting_user"
$DB_PASSWORD    = "ChangeThisStrongPassword123!"  # نفس الباسوورد اللي حطيته في السيرفر
# ============================================================

$ProjectPath = "D:\accounting_system"
$EnvFile = Join-Path $ProjectPath ".env"
$EnvExample = Join-Path $ProjectPath ".env.example"

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  DB Server: $DB_SERVER_IP:$DB_PORT" -ForegroundColor White
Write-Host "  Database: $DB_NAME" -ForegroundColor White
Write-Host "  User: $DB_USER" -ForegroundColor White
Write-Host ""

# Test connection first
Write-Host "Testing connection to PostgreSQL..." -ForegroundColor Cyan
try {
    $TestCmd = "psql"
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        # Try to find psql in PostgreSQL installation
        $PG_PATHS = @(
            "C:\Program Files\PostgreSQL\16\bin\psql.exe",
            "C:\Program Files\PostgreSQL\15\bin\psql.exe",
            "C:\PostgreSQL\16\bin\psql.exe"
        )
        foreach ($p in $PG_PATHS) {
            if (Test-Path $p) { $TestCmd = $p; break }
        }
    }

    $result = & $TestCmd "postgresql://$DB_USER:$DB_PASSWORD@$DB_SERVER_IP:$DB_PORT/$DB_NAME" -c "SELECT 'OK' as status;" -t -A
    if ($result -like "*OK*") {
        Write-Host "  Connection test: SUCCESS" -ForegroundColor Green
    } else {
        Write-Host "  Connection test: FAILED - $result" -ForegroundColor Red
        $continue = Read-Host "Continue anyway? (y/N)"
        if ($continue -ne 'y' -and $continue -ne 'Y') { exit }
    }
} catch {
    Write-Host "  Could not test (psql not found). Will continue..." -ForegroundColor Yellow
}

# Build DATABASE_URL
$DatabaseUrl = "postgresql://$DB_USER:$DB_PASSWORD@$DB_SERVER_IP:$DB_PORT/$DB_NAME"

# Read existing .env or create from example
if (Test-Path $EnvFile) {
    $envContent = Get-Content $EnvFile -Raw -Encoding UTF8
    Write-Host "  Found existing .env, updating..." -ForegroundColor Yellow
} elseif (Test-Path $EnvExample) {
    $envContent = Get-Content $EnvExample -Raw -Encoding UTF8
    Write-Host "  Creating .env from .env.example..." -ForegroundColor Green
} else {
    $envContent = ""
    Write-Host "  Creating new .env..." -ForegroundColor Green
}

# Update or add DATABASE_URL
if ($envContent -match "(?m)^DATABASE_URL\s*=") {
    $envContent = $envContent -replace "(?m)^DATABASE_URL\s*=.*", "DATABASE_URL=$DatabaseUrl"
} else {
    $envContent = $envContent.TrimEnd() + "`r`nDATABASE_URL=$DatabaseUrl`r`n"
}

# Update or add DB_* variables (for Django database config)
$vars = @{
    "DB_ENGINE"   = "django.db.backends.postgresql"
    "DB_NAME"     = $DB_NAME
    "DB_USER"     = $DB_USER
    "DB_PASSWORD" = $DB_PASSWORD
    "DB_HOST"     = $DB_SERVER_IP
    "DB_PORT"     = $DB_PORT
    "DB_OPTIONS"  = "-c search_path=public -c timezone=UTC"
}

foreach ($key in $vars.Keys) {
    $val = $vars[$key]
    if ($envContent -match "(?m)^$key\s*=") {
        $envContent = $envContent -replace "(?m)^$key\s*=.*", "$key=$val"
    } else {
        $envContent += "$key=$val`r`n"
    }
}

# Update ALLOWED_HOSTS to include DB server IP (for health checks)
$allowedHosts = "ALLOWED_HOSTS=localhost,127.0.0.1,$DB_SERVER_IP"
if ($envContent -match "(?m)^ALLOWED_HOSTS\s*=") {
    $envContent = $envContent -replace "(?m)^ALLOWED_HOSTS\s*=.*", $allowedHosts
} else {
    $envContent += "$allowedHosts`r`n"
}

# Update CSRF_TRUSTED_ORIGINS
$csrfOrigins = "CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://$DB_SERVER_IP:8000"
if ($envContent -match "(?m)^CSRF_TRUSTED_ORIGINS\s*=") {
    $envContent = $envContent -replace "(?m)^CSRF_TRUSTED_ORIGINS\s*=.*", $csrfOrigins
} else {
    $envContent += "$csrfOrigins`r`n"
}

# Save
$envContent | Set-Content $EnvFile -Encoding UTF8
Write-Host "`n  .env updated successfully!" -ForegroundColor Green

# Show what was written
Write-Host "`nKey settings in .env:" -ForegroundColor Cyan
$envContent -split "`r?`n" | Where-Object { $_ -match "^(DATABASE_URL|DB_|ALLOWED_HOSTS|CSRF)" } | ForEach-Object {
    if ($_ -like "*PASSWORD*") {
        Write-Host "  $_" -ForegroundColor Yellow
    } else {
        Write-Host "  $_" -ForegroundColor White
    }
}

Write-Host "`nNext steps on THIS device:" -ForegroundColor Cyan
Write-Host "  1. cd $ProjectPath" -ForegroundColor White
Write-Host "  2. venv\Scripts\activate" -ForegroundColor White
Write-Host "  3. pip install psycopg2-binary" -ForegroundColor White
Write-Host "  4. python manage.py migrate" -ForegroundColor White
Write-Host "  5. (On ONE device only) python run_seed.py" -ForegroundColor White
Write-Host "  6. python manage.py collectstatic" -ForegroundColor White
Write-Host "  7. python run_waitress.py" -ForegroundColor White
