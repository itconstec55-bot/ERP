"""
Silent Update: Checks for and applies updates without user intervention.
Supports git-based and file-based update sources.
"""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "accounting_system.settings")

from deployment.config.settings import (
    UPDATES_ENABLED, UPDATES_CHECK_INTERVAL, UPDATES_SOURCE,
    UPDATES_GIT_REPO, UPDATES_GIT_BRANCH,
    UPDATES_INSTALL_DEPS, UPDATES_RUN_MIGRATIONS,
    UPDATES_REQUIRE_RESTART, PYTHON_EXE,
    DEPLOYMENT_DIR, LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT,
)

logger = logging.getLogger("silent_update")

UPDATE_STATE_FILE = Path(DEPLOYMENT_DIR) / "update_state.json"
UPDATES_DIR = Path(DEPLOYMENT_DIR) / "updates"
HASHES_FILE = UPDATES_DIR / "file_hashes.json"


def _load_state():
    import logging
    logger = logging.getLogger('accounting')
    if UPDATE_STATE_FILE.exists():
        try:
            return json.loads(UPDATE_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception('Failed to load update state')
    return {
        "last_check": None,
        "last_update": None,
        "last_version": None,
        "pending_restart": False,
        "update_count": 0,
        "last_error": None,
    }


def _save_state(state):
    UPDATE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_STATE_FILE.write_text(
        json.dumps(state, indent=2, default=str), encoding="utf-8"
    )


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_hashes():
    """Compute SHA-256 of all .py files in the project."""
    hashes = {}
    exclude_dirs = {".git", "__pycache__", "venv", "env", ".tox", "node_modules",
                    "deployment/backups", "deployment/logs", "deployment/updates"}
    for root, dirs, files in os.walk(str(BASE_DIR)):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if f.endswith((".py", ".html", ".json", ".js", ".css")):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, str(BASE_DIR))
                hashes[rel] = _hash_file(full)
    return hashes


def _read_snapshot():
    if HASHES_FILE.exists():
        return json.loads(HASHES_FILE.read_text(encoding="utf-8"))
    return {}


def _write_snapshot(hashes):
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    HASHES_FILE.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


class GitUpdater:
    """Pull updates from a git repository."""

    def __init__(self, repo_path, branch="main"):
        self.repo_path = repo_path
        self.branch = branch

    def _run(self, cmd, cwd=None):
        result = subprocess.run(
            cmd, cwd=cwd or self.repo_path,
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()

    def check_for_updates(self):
        ok, out, err = self._run(["git", "fetch", "origin", self.branch])
        if not ok:
            return None, f"Fetch failed: {err}"

        ok, local_hash, _ = self._run(["git", "rev-parse", "HEAD"])
        if not ok:
            return None, "Cannot get local HEAD"

        ok, remote_hash, _ = self._run(
            ["git", "rev-parse", f"origin/{self.branch}"]
        )
        if not ok:
            return None, "Cannot get remote HEAD"

        if local_hash != remote_hash:
            ok, log_out, _ = self._run(
                ["git", "log", "--oneline", f"HEAD..origin/{self.branch}"]
            )
            commits = log_out.strip().split("\n") if ok and log_out else []
            return {
                "available": True,
                "local": local_hash,
                "remote": remote_hash,
                "commits": len(commits),
                "summary": commits[:10],
            }, None
        return {"available": False, "local": local_hash}, None

    def apply_update(self):
        ok, _, err = self._run(["git", "pull", "origin", self.branch])
        return ok, err


class FileUpdater:
    """Apply updates from a .zip file in the updates directory."""

    def __init__(self):
        self.updates_dir = UPDATES_DIR

    def check_for_updates(self):
        zips = sorted(self.updates_dir.glob("update_*.zip"), reverse=True)
        if not zips:
            return {"available": False}, None
        latest = zips[0]
        return {
            "available": True,
            "file": str(latest),
            "size": latest.stat().st_size,
        }, None

    def apply_update(self, update_info):
        zip_path = Path(update_info["file"])
        try:
            backup = self._backup_current()
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(str(BASE_DIR))
            logger.info(f"Update applied from {zip_path.name}")
            return True, None
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False, str(e)

    def _backup_current(self):
        backup_dir = Path(DEPLOYMENT_DIR) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_zip = backup_dir / f"pre_update_{ts}.zip"
        exclude = {".git", "__pycache__", "venv", "env",
                   "deployment/backups", "deployment/logs"}
        with zipfile.ZipFile(str(backup_zip), "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(str(BASE_DIR)):
                dirs[:] = [d for d in dirs if d not in exclude]
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, str(BASE_DIR))
                    zf.write(full, arc)
        logger.info(f"Pre-update backup: {backup_zip.name}")
        return backup_zip


class UpdateManager:
    """Orchestrates the silent update lifecycle."""

    def __init__(self):
        self.state = _load_state()
        if UPDATES_SOURCE == "git":
            self.updater = GitUpdater(UPDATES_GIT_REPO, UPDATES_GIT_BRANCH)
        else:
            self.updater = FileUpdater()

    def _install_dependencies(self):
        if not UPDATES_INSTALL_DEPS:
            return True
        req_file = BASE_DIR / "requirements.txt"
        if not req_file.exists():
            return True
        ok = subprocess.run(
            [PYTHON_EXE, "-m", "pip", "install", "-r", str(req_file), "-q"],
            capture_output=True, timeout=300,
        ).returncode == 0
        if ok:
            logger.info("Dependencies updated")
        else:
            logger.warning("Dependency update had issues")
        return True

    def _run_migrations(self):
        if not UPDATES_RUN_MIGRATIONS:
            return True
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "accounting_system.settings"
        ok = subprocess.run(
            [PYTHON_EXE, "-m", "django", "migrate", "--no-input"],
            cwd=str(BASE_DIR), env=env, capture_output=True, timeout=120,
        ).returncode == 0
        if ok:
            logger.info("Migrations applied")
        else:
            logger.warning("Migration issues detected")
        return True

    def _collect_static(self):
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "accounting_system.settings"
        subprocess.run(
            [PYTHON_EXE, "-m", "django", "collectstatic", "--no-input"],
            cwd=str(BASE_DIR), env=env, capture_output=True, timeout=60,
        )

    def check_and_update(self):
        if not UPDATES_ENABLED:
            return

        self.state["last_check"] = datetime.now().isoformat()
        logger.info(f"Checking for updates ({UPDATES_SOURCE})...")

        try:
            update_info, error = self.updater.check_for_updates()
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            self.state["last_error"] = str(e)
            _save_state(self.state)
            return

        if error:
            logger.warning(f"Update check error: {error}")
            self.state["last_error"] = error
            _save_state(self.state)
            return

        if not update_info or not update_info.get("available"):
            logger.info("System is up to date")
            self.state["last_error"] = None
            _save_state(self.state)
            return

        logger.info(f"Update available: {json.dumps(update_info, default=str)}")

        # Apply update
        if UPDATES_SOURCE == "git":
            ok, err = self.updater.apply_update()
        else:
            ok, err = self.updater.apply_update(update_info)

        if ok:
            self._install_dependencies()
            self._run_migrations()
            self._collect_static()
            self.state["last_update"] = datetime.now().isoformat()
            self.state["update_count"] += 1
            self.state["pending_restart"] = UPDATES_REQUIRE_RESTART
            self.state["last_error"] = None
            logger.info("Update applied successfully")
        else:
            self.state["last_error"] = err
            logger.error(f"Update failed: {err}")

        _save_state(self.state)

    def run_forever(self):
        logger.info("Silent update manager started")
        while True:
            try:
                self.check_and_update()
            except Exception as e:
                logger.error(f"Update loop error: {e}", exc_info=True)
            time.sleep(UPDATES_CHECK_INTERVAL)


def take_snapshot():
    """Take a file hash snapshot for change detection."""
    hashes = _snapshot_hashes()
    _write_snapshot(hashes)
    logger.info(f"Snapshot saved: {len(hashes)} files")
    return hashes


def detect_changes():
    """Compare current files against last snapshot."""
    old = _read_snapshot()
    new = _snapshot_hashes()
    changed = []
    added = []
    removed = []
    for path, hash_val in new.items():
        if path in old:
            if old[path] != hash_val:
                changed.append(path)
        else:
            added.append(path)
    for path in old:
        if path not in new:
            removed.append(path)
    return {"changed": changed, "added": added, "removed": removed}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                str(Path(LOGS_DIR) / "updates.log"), encoding="utf-8"
            ),
        ],
    )
    manager = UpdateManager()
    manager.run_forever()


if __name__ == "__main__":
    main()
