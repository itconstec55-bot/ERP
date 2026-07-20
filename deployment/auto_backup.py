"""
Automatic Backup: Database and file backup with rotation.
"""
import json
import logging
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "accounting_system.settings")

from deployment.config.settings import (
    BACKUPS_ENABLED, BACKUPS_INTERVAL, BACKUPS_DIR,
    BACKUPS_MAX_COUNT, BACKUPS_DB_PATH,
    LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT,
)

logger = logging.getLogger("auto_backup")

BACKUP_STATE_FILE = Path(BACKUPS_DIR) / "backup_state.json"

EXCLUDE_DIRS = {
    ".git", "__pycache__", "venv", "env", "node_modules",
    "deployment/backups", "deployment/logs", "deployment/updates",
    ".tox", "staticfiles", "media",
}


def _load_state():
    import logging
    logger = logging.getLogger('accounting')
    if BACKUP_STATE_FILE.exists():
        try:
            return json.loads(BACKUP_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception('Failed to load backup state')
    return {"last_backup": None, "backup_count": 0, "last_error": None}


def _save_state(state):
    BACKUP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_STATE_FILE.write_text(
        json.dumps(state, indent=2, default=str), encoding="utf-8"
    )


def backup_database():
    """Create a safe copy of the SQLite database."""
    if not Path(BACKUPS_DB_PATH).exists():
        logger.warning("Database file not found")
        return None

    backup_dir = Path(BACKUPS_DIR) / "database"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"db_{ts}.sqlite3"

    try:
        src = sqlite3.connect(BACKUPS_DB_PATH)
        dst = sqlite3.connect(str(backup_path))
        src.backup(dst)
        src.close()
        dst.close()
        size_kb = backup_path.stat().st_size // 1024
        logger.info(f"Database backup: {backup_path.name} ({size_kb}KB)")
        return backup_path
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return None


def backup_files():
    """Create a zip archive of project files (excluding .git, __pycache__, etc)."""
    backup_dir = Path(BACKUPS_DIR) / "files"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"files_{ts}.zip"

    try:
        with zipfile.ZipFile(str(backup_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(str(BASE_DIR)):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, str(BASE_DIR))
                    zf.write(full, arc)
        size_kb = backup_path.stat().st_size // 1024
        logger.info(f"Files backup: {backup_path.name} ({size_kb}KB)")
        return backup_path
    except Exception as e:
        logger.error(f"Files backup failed: {e}")
        return None


def cleanup_old_backups():
    """Remove backups exceeding the max count."""
    backup_dir = Path(BACKUPS_DIR)
    for sub in ["database", "files"]:
        sub_dir = backup_dir / sub
        if not sub_dir.exists():
            continue
        files = sorted(sub_dir.iterdir(), key=lambda f: f.stat().st_mtime)
        while len(files) > BACKUPS_MAX_COUNT:
            oldest = files.pop(0)
            oldest.unlink()
            logger.info(f"Removed old backup: {oldest.name}")


def full_backup():
    """Run a complete backup cycle."""
    logger.info("Starting full backup...")

    db_result = backup_database()
    files_result = backup_files()
    cleanup_old_backups()

    state = _load_state()
    state["last_backup"] = datetime.now().isoformat()
    state["backup_count"] += 1
    state["last_error"] = None
    _save_state(state)

    success = db_result is not None
    logger.info(
        f"Backup complete: db={'OK' if db_result else 'FAIL'}, "
        f"files={'OK' if files_result else 'FAIL'}"
    )
    return success


def restore_database(backup_name=None):
    """Restore database from a backup."""
    db_dir = Path(BACKUPS_DIR) / "database"
    if not db_dir.exists():
        logger.error("No database backups found")
        return False

    if backup_name:
        src = db_dir / backup_name
    else:
        backups = sorted(db_dir.glob("db_*.sqlite3"), key=lambda f: f.stat().st_mtime)
        if not backups:
            logger.error("No database backups found")
            return False
        src = backups[-1]

    if not src.exists():
        logger.error(f"Backup not found: {src}")
        return False

    try:
        dest = Path(BACKUPS_DB_PATH)
        shutil.copy2(str(src), str(dest))
        logger.info(f"Database restored from: {src.name}")
        return True
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def run_forever():
    """Main backup loop."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                str(Path(LOGS_DIR) / "backup.log"), encoding="utf-8"
            ),
        ],
    )
    logger.info("Auto-backup service started")
    while True:
        try:
            if BACKUPS_ENABLED:
                full_backup()
        except Exception as e:
            logger.error(f"Backup error: {e}", exc_info=True)
        time.sleep(BACKUPS_INTERVAL)


if __name__ == "__main__":
    run_forever()
