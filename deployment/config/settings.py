"""
Config: Deployment and Service Configuration for Accounting System
All settings in one place for easy management.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─── Server ──────────────────────────────────────────────────────
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "2"))
SERVER_TIMEOUT = int(os.getenv("SERVER_TIMEOUT", "120"))

# ─── Health Check ────────────────────────────────────────────────
HEALTH_CHECK_ENABLED = True
HEALTH_CHECK_INTERVAL = 30          # seconds between checks
HEALTH_CHECK_TIMEOUT = 10           # max seconds to wait for response
HEALTH_CHECK_FAIL_THRESHOLD = 3     # consecutive failures before restart
HEALTH_CHECK_ENDPOINTS = [
    "/",
    "/accounts/",
    "/purchases/suppliers/",
    "/reports/",
]
HEALTH_CHECK_EXPECTED_STATUS = 200

# ─── Auto Restart ────────────────────────────────────────────────
RESTART_ENABLED = True
RESTART_COOLDOWN = 60               # min seconds between restarts
RESTART_MAX_ATTEMPTS = 5            # max restarts before giving up
RESTART_BACKOFF_MULTIPLIER = 2.0    # exponential backoff multiplier
RESTART_COOLDOWN_RESET_AFTER = 300  # reset counter after 5 min of healthy

# ─── Silent Updates ──────────────────────────────────────────────
UPDATES_ENABLED = True
UPDATES_CHECK_INTERVAL = 3600       # check every hour
UPDATES_SOURCE = "git"              # git | file | none
UPDATES_GIT_REPO = str(BASE_DIR)
UPDATES_GIT_BRANCH = "main"
UPDATES_INSTALL_DEPS = True
UPDATES_RUN_MIGRATIONS = True
UPDATES_REQUIRE_RESTART = False     # auto-restart after update

# ─── Backups ─────────────────────────────────────────────────────
BACKUPS_ENABLED = True
BACKUPS_INTERVAL = 7200             # every 2 hours
BACKUPS_DIR = str(BASE_DIR / "deployment" / "backups")
BACKUPS_MAX_COUNT = 30              # keep last 30 backups
BACKUPS_DB_PATH = str(BASE_DIR / "db.sqlite3")

# ─── Alerts ──────────────────────────────────────────────────────
ALERTS_ENABLED = True
ALERTS_METHOD = "log"               # log | email | both
ALERTS_LOG_DIR = str(BASE_DIR / "deployment" / "logs")
ALERTS_EMAIL_SMTP = os.getenv("SMTP_HOST", "")
ALERTS_EMAIL_PORT = int(os.getenv("SMTP_PORT", "587"))
ALERTS_EMAIL_USER = os.getenv("SMTP_USER", "")
ALERTS_EMAIL_PASS = os.getenv("SMTP_PASS", "")
ALERTS_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")
ALERTS_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "noreply@accounting.local")

# ─── Paths ───────────────────────────────────────────────────────
DEPLOYMENT_DIR = str(BASE_DIR / "deployment")
LOGS_DIR = str(BASE_DIR / "deployment" / "logs")
PYTHON_EXE = os.getenv("PYTHON_EXE", "python")
DJANGO_SETTINGS_MODULE = "accounting_system.settings"

# ─── Logging ─────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
