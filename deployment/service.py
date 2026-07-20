"""
Service Runner: Orchestrates all deployment services.
Run this single script to start the full system:
  - Django server
  - Health monitor (auto-restart on failure)
  - Silent updater (check + apply updates)
  - Auto-backup (database + files)
  - Alerts (log + optional email)
"""
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "accounting_system.settings")

from deployment.config.settings import (
    SERVER_HOST, SERVER_PORT, PYTHON_EXE,
    HEALTH_CHECK_ENABLED, HEALTH_CHECK_INTERVAL,
    UPDATES_ENABLED, UPDATES_CHECK_INTERVAL,
    BACKUPS_ENABLED, BACKUPS_INTERVAL,
    LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT,
    DEPLOYMENT_DIR, DJANGO_SETTINGS_MODULE,
)

logger = logging.getLogger("service")

shutdown_event = threading.Event()


def setup_logging():
    logs_dir = Path(LOGS_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                str(logs_dir / "service.log"), encoding="utf-8"
            ),
        ],
    )


# ─── Django Server Thread ───────────────────────────────────────
def run_django_server():
    """Run the Django development server."""
    import subprocess
    cmd = [PYTHON_EXE, str(BASE_DIR / "run_server.py")]
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )
        logger.info(f"Django server started (PID {proc.pid})")
        while not shutdown_event.is_set():
            if proc.poll() is not None:
                logger.warning("Django server died, restarting...")
                proc = subprocess.Popen(
                    cmd, cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32" else 0
                    ),
                )
                logger.info(f"Django server restarted (PID {proc.pid})")
            time.sleep(5)
        proc.terminate()
        proc.wait(timeout=10)
    except Exception as e:
        logger.error(f"Django server error: {e}", exc_info=True)


# ─── Health Check Thread ────────────────────────────────────────
def run_health_check():
    """Periodically check server health."""
    import urllib.request
    import urllib.error

    consecutive_failures = 0
    threshold = 3
    base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"

    time.sleep(10)
    while not shutdown_event.is_set():
        try:
            req = urllib.request.Request(base_url + "/")
            req.add_header("User-Agent", "AccountingSystem-HealthCheck/1.0")
            resp = urllib.request.urlopen(req, timeout=10)
            status = resp.getcode()
            if status == 200:
                if consecutive_failures > 0:
                    logger.info("Health check: OK (recovered)")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Health check: unexpected status {status}")
        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"Health check failed ({consecutive_failures}): {e}")

        if consecutive_failures >= threshold:
            logger.error(
                f"Health check: {consecutive_failures} consecutive failures"
            )
            from deployment.alerts import alert_health_check_failed
            alert_health_check_failed(consecutive_failures, threshold)
            consecutive_failures = 0

        shutdown_event.wait(HEALTH_CHECK_INTERVAL)


# ─── Update Thread ──────────────────────────────────────────────
def run_updater():
    """Periodically check for and apply updates."""
    if not UPDATES_ENABLED:
        return

    from deployment.silent_update import UpdateManager

    time.sleep(30)
    while not shutdown_event.is_set():
        try:
            manager = UpdateManager()
            manager.check_and_update()
        except Exception as e:
            logger.error(f"Update check error: {e}", exc_info=True)
        shutdown_event.wait(UPDATES_CHECK_INTERVAL)


# ─── Backup Thread ──────────────────────────────────────────────
def run_backup():
    """Periodically create database and file backups."""
    if not BACKUPS_ENABLED:
        return

    from deployment.auto_backup import full_backup

    time.sleep(60)
    while not shutdown_event.is_set():
        try:
            full_backup()
        except Exception as e:
            logger.error(f"Backup error: {e}", exc_info=True)
        shutdown_event.wait(BACKUPS_INTERVAL)


# ─── Status Command ─────────────────────────────────────────────
def show_status():
    """Print current system status."""
    import urllib.request
    base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"

    print("=" * 60)
    print("  Accounting System - Service Status")
    print("=" * 60)

    # Check server
    try:
        req = urllib.request.Request(base_url + "/")
        resp = urllib.request.urlopen(req, timeout=5)
        print(f"  Server:    UP   (HTTP {resp.getcode()})")
    except Exception:
        print("  Server:    DOWN")

    # Check health state
    state_file = Path(DEPLOYMENT_DIR) / "health_state.json"
    if state_file.exists():
        import json
        state = json.loads(state_file.read_text(encoding="utf-8"))
        print(f"  Failures:  {state.get('consecutive_failures', 0)}")
        print(f"  Restarts:  {state.get('total_restarts', 0)}")
        print(f"  Last OK:   {state.get('last_healthy', 'never')}")

    # Check update state
    update_file = Path(DEPLOYMENT_DIR) / "update_state.json"
    if update_file.exists():
        import json
        state = json.loads(update_file.read_text(encoding="utf-8"))
        print(f"  Updates:   {state.get('update_count', 0)} applied")
        print(f"  Last chk:  {state.get('last_check', 'never')}")

    # Check backup state
    backup_file = Path(DEPLOYMENT_DIR) / "backups" / "backup_state.json"
    if backup_file.exists():
        import json
        state = json.loads(backup_file.read_text(encoding="utf-8"))
        print(f"  Backups:   {state.get('backup_count', 0)} created")
        print(f"  Last bkp:  {state.get('last_backup', 'never')}")

    print("=" * 60)


# ─── Main ───────────────────────────────────────────────────────
def main():
    setup_logging()

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_status()
        return

    logger.info("=" * 60)
    logger.info("  Accounting System - Service Starting")
    logger.info(f"  Server: {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    def signal_handler(sig, frame):
        logger.info("Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    threads = []
    threads.append(
        threading.Thread(target=run_django_server, name="django", daemon=True)
    )
    if HEALTH_CHECK_ENABLED:
        threads.append(
            threading.Thread(target=run_health_check, name="health", daemon=True)
        )
    if UPDATES_ENABLED:
        threads.append(
            threading.Thread(target=run_updater, name="updater", daemon=True)
        )
    if BACKUPS_ENABLED:
        threads.append(
            threading.Thread(target=run_backup, name="backup", daemon=True)
        )

    for t in threads:
        t.start()
        logger.info(f"Thread started: {t.name}")

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(1)
    except KeyboardInterrupt:
        shutdown_event.set()

    logger.info("Shutting down...")
    for t in threads:
        t.join(timeout=15)
    logger.info("Service stopped")


if __name__ == "__main__":
    main()
