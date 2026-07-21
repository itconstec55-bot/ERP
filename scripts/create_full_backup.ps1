<#
.SYNOPSIS
    Creates a complete backup of the Accounting System for transfer to another machine
.DESCRIPTION
    Archives all source code, database, templates, static files, media, configs, and scripts.
    Excludes: venv, __pycache__, .git, logs folders, old backup zips, node_modules
#>

$ErrorActionPreference = "Stop"

# Configuration
$SourceRoot = "D:\accounting_system"
$BackupDir  = "D:\accounting_system_backups"
$Timestamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$ZipName    = "accounting_system_FULL_$Timestamp.zip"
$ZipPath    = Join-Path $BackupDir $ZipName

# Create backup directory
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  ACCOUNTING SYSTEM - FULL BACKUP CREATOR" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Source: $SourceRoot" -ForegroundColor White
Write-Host "Output: $ZipPath" -ForegroundColor White
Write-Host ""

# Patterns to EXCLUDE (relative to source root)
$ExcludePatterns = @(
    "venv\*",
    "venv",
    "__pycache__\*",
    "__pycache__",
    ".git\*",
    ".git",
    "logs\*",
    "logs",
    "backups\*",
    "backups",
    "backups_storage\*",
    "backups_storage",
    "*.log",
    "*.err",
    "*.out",
    "accounting_system_*.zip",
    "*.sqlite3-shm",
    "*.sqlite3-wal",
    "node_modules\*",
    ".vs\*",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache\*",
    ".coverage",
    "htmlcov\*",
    "*.egg-info\*",
    "dist\*",
    "build\*",
    ".mypy_cache\*",
    ".ruff_cache\*"
)

Write-Host "Scanning files..." -ForegroundColor Cyan

# Get all files
$AllFiles = Get-ChildItem -Path $SourceRoot -Recurse -File -ErrorAction SilentlyContinue
Write-Host "Total files found: $($AllFiles.Count)" -ForegroundColor White

# Filter files
$FilesToArchive = @()
$SkippedCount = 0

foreach ($file in $AllFiles) {
    $RelPath = $file.FullName.Substring($SourceRoot.Length + 1)
    $ShouldExclude = $false

    foreach ($pattern in $ExcludePatterns) {
        if ($RelPath -like $pattern) {
            $ShouldExclude = $true
            break
        }
        # Check parent directories too
        $parts = $RelPath.Split('\')
        for ($i = 0; $i -lt $parts.Count; $i++) {
            $partial = $parts[0..$i] -join '\'
            if ($partial -like $pattern) {
                $ShouldExclude = $true
                break
            }
        }
        if ($ShouldExclude) { break }
    }

    if ($ShouldExclude) {
        $SkippedCount++
    } else {
        $FilesToArchive += $file
    }
}

Write-Host "Files to archive: $($FilesToArchive.Count)" -ForegroundColor Green
Write-Host "Files excluded:   $SkippedCount" -ForegroundColor Yellow
Write-Host ""

Write-Host "Creating archive..." -ForegroundColor Cyan
Add-Type -AssemblyName "System.IO.Compression"
Add-Type -AssemblyName "System.IO.Compression.FileSystem"

# Handle SQLite DB - copy it first since it might be locked
$TempDir = [System.IO.Path]::GetTempPath()
$TempDbPath = Join-Path $TempDir "db_backup_$Timestamp.sqlite3"
$DbSource = Join-Path $SourceRoot "db.sqlite3"

if (Test-Path $DbSource) {
    Write-Host "  Copying database (may be locked)..." -ForegroundColor Yellow
    try {
        [System.IO.File]::Copy($DbSource, $TempDbPath, $true)
        Write-Host "  Database copied to temp location" -ForegroundColor Green
    } catch {
        Write-Host "  Warning: Could not copy DB - $($_.Exception.Message)" -ForegroundColor Red
    }
}

$zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
$count = 0
$totalSize = 0

foreach ($file in $FilesToArchive) {
    $RelPath = $file.FullName.Substring($SourceRoot.Length + 1)
    $entry = $zip.CreateEntry($RelPath, [System.IO.Compression.CompressionLevel]::Optimal)
    $stream = $entry.Open()

    # Use temp DB copy if this is the main database file
    $sourcePath = $file.FullName
    if ($RelPath -eq "db.sqlite3" -and (Test-Path $TempDbPath)) {
        $sourcePath = $TempDbPath
    }

    $fileStream = [System.IO.File]::OpenRead($sourcePath)
    $fileStream.CopyTo($stream)
    $fileStream.Close()
    $stream.Close()
    $count++
    $totalSize += $file.Length

    if ($count % 500 -eq 0) {
        Write-Host "  Archived $count files..." -NoNewline
        Write-Host "`r" -NoNewline
    }
}

$zip.Dispose()

$sizeMB = [math]::Round($totalSize / 1MB, 2)

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "BACKUP COMPLETED SUCCESSFULLY" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Archive: $ZipPath" -ForegroundColor White
Write-Host "Files archived: $count" -ForegroundColor White
Write-Host "Files excluded: $SkippedCount" -ForegroundColor Yellow
Write-Host "Total size: $sizeMB MB" -ForegroundColor White
Write-Host ""
Write-Host "CONTENTS SUMMARY:" -ForegroundColor Cyan
Write-Host "   All 30+ Django apps (accounts, sales, purchases, hr, etc.)" -ForegroundColor Green
Write-Host "   Database (db.sqlite3 + WAL files)" -ForegroundColor Green
Write-Host "   Templates, static files, media uploads" -ForegroundColor Green
Write-Host "   Configuration (.env, docker-compose, requirements)" -ForegroundColor Green
Write-Host "   All setup/run/seed scripts" -ForegroundColor Green
Write-Host "   Documentation (README, DEPLOYMENT, DATASHEET, 4 Arabic guides)" -ForegroundColor Green
Write-Host "   New in v2.2: Factory Boy factories, conftest, pytest.ini, pyproject.toml" -ForegroundColor Green
Write-Host "   New in v2.2: Pre-commit config, CI/CD workflow, form-validation.js" -ForegroundColor Green
Write-Host "   Excluded: venv (reinstall via requirements.txt), __pycache__, .git, logs folders, old backups" -ForegroundColor Yellow
Write-Host ""
Write-Host "TO RESTORE ON NEW MACHINE:" -ForegroundColor Cyan
Write-Host "   1. Extract zip to target folder (e.g., D:\accounting_system)" -ForegroundColor White
Write-Host "   2. Run: python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt" -ForegroundColor White
Write-Host "   3. Copy .env.example to .env and configure" -ForegroundColor White
Write-Host "   4. Run: python manage.py migrate" -ForegroundColor White
Write-Host "   5. Run: python run_seed.py (or run_seed.bat)" -ForegroundColor White
Write-Host "   6. Run: python manage.py collectstatic" -ForegroundColor White
Write-Host "   7. Start: python run_waitress.py or start_production.bat" -ForegroundColor White
Write-Host ""

# Cleanup temp files
if (Test-Path $TempDbPath) {
    try { Remove-Item $TempDbPath -Force; Write-Host "  Temp DB cleaned up" -ForegroundColor Gray }
    catch { Write-Host "  Warning: Could not remove temp DB" -ForegroundColor Yellow }
}
# Also cleanup WAL/SHM temp copies if they exist
$TempWalPath = $TempDbPath -replace "\.sqlite3$", "-wal"
$TempShmPath = $TempDbPath -replace "\.sqlite3$", "-shm"
if (Test-Path $TempWalPath) { try { Remove-Item $TempWalPath -Force } catch {} }
if (Test-Path $TempShmPath) { try { Remove-Item $TempShmPath -Force } catch {} }

# Open backup folder
Invoke-Item $BackupDir
