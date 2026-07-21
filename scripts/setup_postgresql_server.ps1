<#
.SYNOPSIS
    Installs and configures PostgreSQL 16 as a central database server for Accounting System
.DESCRIPTION
    Run on the machine that will host the database (can be one of the two devices or a separate server).
    Creates database, users, enables remote connections, configures firewall.
.NOTES
    Run as Administrator on the DATABASE SERVER machine.
#>

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  PostgreSQL 16 Setup for Accounting System" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# CONFIGURATION - غيّر هذه القيم قبل التشغيل
# ============================================================
$DB_NAME        = "accounting_db"
$DB_USER        = "accounting_user"
$DB_PASSWORD    = "ChangeThisStrongPassword123!"  # غيّر هذا!
$DB_PORT        = 5432
$PG_VERSION     = "16"
$ALLOW_CIDR     = "0.0.0.0/0"  # أو حدده: "192.168.1.0/24" لشبكتك فقط
# ============================================================

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Database: $DB_NAME" -ForegroundColor White
Write-Host "  User: $DB_USER" -ForegroundColor White
Write-Host "  Port: $DB_PORT" -ForegroundColor White
Write-Host "  Allow from: $ALLOW_CIDR" -ForegroundColor White
Write-Host ""

# Confirm
$confirm = Read-Host "Continue with these settings? (y/N)"
if ($confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit
}

# -----------------------------------------------------------------
# 1. INSTALL POSTGRESQL (via winget or chocolatey)
# -----------------------------------------------------------------
Write-Host "`n[1/6] Installing PostgreSQL $PG_VERSION..." -ForegroundColor Cyan

if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id PostgreSQL.PostgreSQL --version $PG_VERSION --accept-source-agreements --accept-package-agreements
}
elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    choco install postgresql --version=$PG_VERSION -y
}
else {
    Write-Host "ERROR: Neither winget nor chocolatey found. Install PostgreSQL manually from postgresql.org" -ForegroundColor Red
    exit 1
}

# Find PostgreSQL installation path
$PG_PATHS = @(
    "C:\Program Files\PostgreSQL\$PG_VERSION",
    "C:\Program Files\PostgreSQL\$PG_VERSION\bin",
    "C:\PostgreSQL\$PG_VERSION\bin"
)
$PG_BIN = $null
foreach ($p in $PG_PATHS) {
    if (Test-Path (Join-Path $p "psql.exe")) { $PG_BIN = $p; break }
}
if (-not $PG_BIN) {
    Write-Host "ERROR: PostgreSQL bin folder not found. Check installation." -ForegroundColor Red
    exit 1
}
Write-Host "  Found PostgreSQL at: $PG_BIN" -ForegroundColor Green

# -----------------------------------------------------------------
# 2. INITIALIZE DATABASE CLUSTER (if not done by installer)
# -----------------------------------------------------------------
Write-Host "`n[2/6] Initializing database cluster..." -ForegroundColor Cyan
$PG_DATA = "C:\Program Files\PostgreSQL\$PG_VERSION\data"
if (-not (Test-Path (Join-Path $PG_DATA "postgresql.conf"))) {
    & "$PG_BIN\initdb.exe" -D $PG_DATA -U postgres -A scram-sha-256 -E UTF8 --locale=C
    Write-Host "  Cluster initialized." -ForegroundColor Green
} else {
    Write-Host "  Cluster already exists." -ForegroundColor Yellow
}

# -----------------------------------------------------------------
# 3. START POSTGRESQL SERVICE
# -----------------------------------------------------------------
Write-Host "`n[3/6] Starting PostgreSQL service..." -ForegroundColor Cyan
$ServiceName = "postgresql-x64-$PG_VERSION"
if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
    Set-Service $ServiceName -StartupType Automatic
    Start-Service $ServiceName -ErrorAction SilentlyContinue
    Start-Sleep 3
    Write-Host "  Service started." -ForegroundColor Green
} else {
    Write-Host "  Service not found, trying to register..." -ForegroundColor Yellow
    & "$PG_BIN\pg_ctl.exe" register -N $ServiceName -D $PG_DATA -w
    Start-Service $ServiceName
    Start-Sleep 3
}

# -----------------------------------------------------------------
# 4. CONFIGURE REMOTE ACCESS (postgresql.conf & pg_hba.conf)
# -----------------------------------------------------------------
Write-Host "`n[4/6] Configuring remote access..." -ForegroundColor Cyan

$ConfFile = Join-Path $PG_DATA "postgresql.conf"
$HbaFile  = Join-Path $PG_DATA "pg_hba.conf"

# Backup originals
Copy-Item $ConfFile "$ConfFile.backup_$(Get-Date -Format 'yyyyMMdd')" -Force
Copy-Item $HbaFile "$HbaFile.backup_$(Get-Date -Format 'yyyyMMdd')" -Force

# postgresql.conf - listen on all interfaces
$conf = Get-Content $ConfFile -Raw
$conf = $conf -replace "#?listen_addresses\s*=\s*'.*'", "listen_addresses = '*'"
$conf = $conf -replace "#?port\s*=\s*\d+", "port = $DB_PORT"
$conf = $conf -replace "#?max_connections\s*=\s*\d+", "max_connections = 100"
$conf = $conf -replace "#?shared_buffers\s*=\s*\d+[A-Z]?", "shared_buffers = 256MB"
$conf = $conf -replace "#?effective_cache_size\s*=\s*\d+[A-Z]?", "effective_cache_size = 1GB"
$conf = $conf -replace "#?maintenance_work_mem\s*=\s*\d+[A-Z]?", "maintenance_work_mem = 64MB"
$conf = $conf -replace "#?wal_buffers\s*=\s*\d+[A-Z]?", "wal_buffers = 16MB"
$conf = $conf -replace "#?checkpoint_completion_target\s*=\s*[\d.]+", "checkpoint_completion_target = 0.9"
$conf = $conf -replace "#?random_page_cost\s*=\s*[\d.]+", "random_page_cost = 1.1"  # SSD
$conf | Set-Content $ConfFile -Encoding UTF8
Write-Host "  postgresql.conf updated." -ForegroundColor Green

# pg_hba.conf - allow remote connections
$hba = Get-Content $HbaFile -Raw
# Add rule for our network (insert after local connections)
$newRule = @"
# Accounting System - Remote access from application servers
host    $DB_NAME        $DB_USER        $ALLOW_CIDR           scram-sha-256
host    all             postgres        $ALLOW_CIDR           scram-sha-256
"@

if ($hba -notlike "*$DB_USER*") {
    $hba = $hba -replace "(# IPv4 local connections:\r?\n)", "`$1$newRule`r`n"
    $hba | Set-Content $HbaFile -Encoding UTF8
    Write-Host "  pg_hba.conf updated." -ForegroundColor Green
} else {
    Write-Host "  Rules already exist." -ForegroundColor Yellow
}

# -----------------------------------------------------------------
# 5. CREATE DATABASE AND USER
# -----------------------------------------------------------------
Write-Host "`n[5/6] Creating database and user..." -ForegroundColor Cyan

$SQL = @"
-- Create user
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD';
    ELSE
        ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Connect to the new database and grant schema privileges
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
"@

$SQLFile = "$env:TEMP\create_db_$(Get-Date -Format 'yyyyMMdd').sql"
$SQL | Set-Content $SQLFile -Encoding UTF8

& "$PG_BIN\psql.exe" -U postgres -f $SQLFile
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Database and user created successfully." -ForegroundColor Green
} else {
    Write-Host "  ERROR creating database. Check if postgres user has password set." -ForegroundColor Red
    Write-Host "  You may need to run manually:" -ForegroundColor Yellow
    Write-Host "  & '$PG_BIN\psql.exe' -U postgres -f $SQLFile" -ForegroundColor White
}

# -----------------------------------------------------------------
# 6. FIREWALL RULE
# -----------------------------------------------------------------
Write-Host "`n[6/6] Configuring Windows Firewall..." -ForegroundColor Cyan

$RuleName = "PostgreSQL $PG_VERSION (Port $DB_PORT)"
if (-not (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Protocol TCP -LocalPort $DB_PORT -Action Allow -Profile Domain,Private,Public
    Write-Host "  Firewall rule created." -ForegroundColor Green
} else {
    Write-Host "  Firewall rule already exists." -ForegroundColor Yellow
}

# -----------------------------------------------------------------
# RESTART SERVICE TO APPLY CONFIG
# -----------------------------------------------------------------
Write-Host "`nRestarting PostgreSQL to apply changes..." -ForegroundColor Cyan
Restart-Service $ServiceName -Force
Start-Sleep 3

# -----------------------------------------------------------------
# TEST CONNECTION
# -----------------------------------------------------------------
Write-Host "`nTesting connection..." -ForegroundColor Cyan
$TestSQL = "SELECT version();"
$TestFile = "$env:TEMP\test_conn.sql"
$TestSQL | Set-Content $TestFile -Encoding UTF8

$result = & "$PG_BIN\psql.exe" -U $DB_USER -d $DB_NAME -h localhost -f $TestFile
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Local connection: OK" -ForegroundColor Green
} else {
    Write-Host "  Local connection: FAILED" -ForegroundColor Red
}

# ============================================================
# SUMMARY
# ============================================================
$ServerIP = (Test-Connection -ComputerName (hostname) -Count 1).IPV4Address.IPAddressToString

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "  POSTGRESQL SETUP COMPLETE" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "CONNECTION DETAILS (save these!):" -ForegroundColor Yellow
Write-Host "  Server IP: $ServerIP" -ForegroundColor White
Write-Host "  Port: $DB_PORT" -ForegroundColor White
Write-Host "  Database: $DB_NAME" -ForegroundColor White
Write-Host "  User: $DB_USER" -ForegroundColor White
Write-Host "  Password: $DB_PASSWORD" -ForegroundColor White
Write-Host ""
Write-Host "DATABASE URL for .env:" -ForegroundColor Cyan
Write-Host "  DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@$ServerIP:$DB_PORT/$DB_NAME" -ForegroundColor White
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Copy the DATABASE_URL above to .env on BOTH devices" -ForegroundColor White
Write-Host "  2. On each device: python manage.py migrate" -ForegroundColor White
Write-Host "  3. On ONE device: python run_seed.py" -ForegroundColor White
Write-Host "  4. Start both devices" -ForegroundColor White
Write-Host ""
Write-Host "CONFIG FILES LOCATION:" -ForegroundColor Cyan
Write-Host "  $ConfFile" -ForegroundColor White
Write-Host "  $HbaFile" -ForegroundColor White
Write-Host ""
Write-Host "TO ALLOW MORE IPs: Edit pg_hba.conf and restart service" -ForegroundColor Yellow

# Save connection info to file
$Info = @"
PostgreSQL Connection Info - $(Get-Date)
Server IP: $ServerIP
Port: $DB_PORT
Database: $DB_NAME
User: $DB_USER
Password: $DB_PASSWORD
DATABASE_URL: postgresql://$DB_USER:$DB_PASSWORD@$ServerIP:$DB_PORT/$DB_NAME
"@
$InfoPath = "$env:USERPROFILE\Desktop\PostgreSQL_Connection_Info.txt"
$Info | Set-Content $InfoPath -Encoding UTF8
Write-Host "Connection info saved to: $InfoPath" -ForegroundColor Green
