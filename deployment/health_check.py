"""
Health Check: Monitors Django server availability and triggers auto-restart.
"""
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "accounting_system.settings")

from deployment.config.settings import (
    SERVER_HOST, SERVER_PORT, HEALTH_CHECK_ENABLED,
    HEALTH_CHECK_INTERVAL, HEALTH_CHECK_TIMEOUT,
    HEALTH_CHECK_FAIL_THRESHOLD, HEALTH_CHECK_ENDPOINTS,
    HEALTH_CHECK_EXPECTED_STATUS, RESTART_ENABLED,
    RESTART_COOLDOWN, RESTART_MAX_ATTEMPTS,
    RESTART_BACKOFF_MULTIPLIER, RESTART_COOLDOWN_RESET_AFTER,
    PYTHON_EXE, LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT,
)

logger = logging.getLogger("health_check")

STATE_FILE = BASE_DIR / "deployment" / "health_state.json"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_state():
    import logging
    logger = logging.getLogger('accounting')
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception('Failed to load health state')
    return {
        "consecutive_failures": 0,
        "total_restarts": 0,
        "last_restart": None,
        "last_healthy": None,
        "last_check": None,
        "server_pid": None,
        "current_backoff": RESTART_COOLDOWN,
    }


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def check_endpoints():
    """Check all configured endpoints. Returns (ok, details)."""
    base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    results = []
    all_ok = True

    for endpoint in HEALTH_CHECK_ENDPOINTS:
        url = base_url + endpoint
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "AccountingSystem-HealthCheck/1.0")
            resp = urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT)
            status = resp.getcode()
            ok = status == HEALTH_CHECK_EXPECTED_STATUS
            results.append({"endpoint": endpoint, "status": status, "ok": ok})
            if not ok:
                all_ok = False
        except urllib.error.HTTPError as e:
            results.append({"endpoint": endpoint, "status": e.code, "ok": False})
            all_ok = False
        except Exception as e:
            results.append({"endpoint": endpoint, "error": str(e), "ok": False})
            all_ok = False

    return all_ok, results


def check_database():
    """Check database connectivity via Django ORM."""
    try:
        import django
        django.setup()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True, "OK"
    except Exception as e:
        return False, str(e)


def check_disk_space(min_mb=500):
    """Check available disk space."""
    try:
        import shutil
        usage = shutil.disk_usage(str(BASE_DIR))
        free_mb = usage.free // (1024 * 1024)
        return free_mb >= min_mb, f"{free_mb}MB free (min: {min_mb}MB)"
    except Exception as e:
        return True, f"Cannot check: {e}"


def check_python_packages():
    """Check critical packages are installed."""
    required = ["django", "psycopg2"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return len(missing) == 0, f"Missing: {missing}" if missing else "All OK"


def full_health_check():
    """Run all health checks. Returns overall status + details."""
    checks = {}

    # 1. HTTP endpoint check
    http_ok, http_details = check_endpoints()
    checks["http"] = {"ok": http_ok, "details": http_details}

    # 2. Database check
    db_ok, db_msg = check_database()
    checks["database"] = {"ok": db_ok, "message": db_msg}

    # 3. Disk space
    disk_ok, disk_msg = check_disk_space()
    checks["disk"] = {"ok": disk_ok, "message": disk_msg}

    overall = all(c["ok"] for c in checks.values())
    return overall, checks


class ProcessManager:
    """Manages the Django server process."""

    def __init__(self):
        self.process = None

    def start(self):
        """Start the Django server."""
        cmd = [PYTHON_EXE, str(BASE_DIR / "run_server.py")]
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
            )
            logger.info(f"Server started with PID {self.process.pid}")
            time.sleep(3)
            return self.process.poll() is None
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    def stop(self):
        """Stop the Django server."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            logger.info("Server stopped")

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def restart(self):
        self.stop()
        time.sleep(2)
        return self.start()


class HealthMonitor:
    """Main health monitoring loop."""

    def __init__(self):
        self.state = _load_state()
        self.pm = ProcessManager()

    def _should_restart(self):
        if not RESTART_ENABLED:
            return False
        if self.state["total_restarts"] >= RESTART_MAX_ATTEMPTS:
            logger.error(
                f"Max restarts ({RESTART_MAX_ATTEMPTS}) reached. Manual intervention required."
            )
            return False
        if self.state["last_restart"]:
            elapsed = (datetime.now() - datetime.fromisoformat(
                self.state["last_restart"]
            )).total_seconds()
            if elapsed < self.state.get("current_backoff", RESTART_COOLDOWN):
                return False
        return True

    def _do_restart(self):
        logger.warning(
            f"Restarting server (attempt {self.state['total_restarts'] + 1})"
        )
        success = self.pm.restart()

        self.state["total_restarts"] += 1
        self.state["last_restart"] = _now()
        self.state["consecutive_failures"] = 0

        if not success:
            self.state["current_backoff"] = (
                self.state.get("current_backoff", RESTART_COOLDOWN)
                * RESTART_BACKOFF_MULTIPLIER
            )
            logger.error("Restart failed, increasing backoff")
        else:
            self.state["current_backoff"] = RESTART_COOLDOWN
            logger.info("Restart successful")

        _save_state(self.state)
        return success

    def _log_check(self, ok, checks):
        level = logging.INFO if ok else logging.WARNING
        logger.log(level, f"Health check: {'PASS' if ok else 'FAIL'}")
        for name, check in checks.items():
            status = "OK" if check.get("ok") else "FAIL"
            logger.log(level, f"  {name}: {status}")

    def run_once(self):
        self.state["last_check"] = _now()

        # Check if server process is alive (if we started it)
        if self.pm.process and not self.pm.is_running():
            logger.warning("Server process died!")
            self.state["consecutive_failures"] += 1

        # Run HTTP + DB checks
        ok, checks = full_health_check()
        self._log_check(ok, checks)

        if ok:
            self.state["consecutive_failures"] = 0
            self.state["last_healthy"] = _now()
            if self.state["total_restarts"] > 0:
                elapsed = (datetime.now() - datetime.fromisoformat(
                    self.state["last_healthy"]
                )).total_seconds()
                if elapsed > RESTART_COOLDOWN_RESET_AFTER:
                    self.state["total_restarts"] = max(
                        0, self.state["total_restarts"] - 1
                    )
        else:
            self.state["consecutive_failures"] += 1
            logger.warning(
                f"Consecutive failures: "
                f"{self.state['consecutive_failures']}/{HEALTH_CHECK_FAIL_THRESHOLD}"
            )
            if (
                self.state["consecutive_failures"] >= HEALTH_CHECK_FAIL_THRESHOLD
                and self._should_restart()
            ):
                self._do_restart()

        _save_state(self.state)
        return ok

    def run_forever(self):
        """Main loop."""
        logger.info("Health monitor started")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)
            time.sleep(HEALTH_CHECK_INTERVAL)

    def get_status(self):
        """Return current status as dict for reporting."""
        self.state = _load_state()
        return {
            "healthy": self.state["consecutive_failures"] == 0,
            "consecutive_failures": self.state["consecutive_failures"],
            "total_restarts": self.state["total_restarts"],
            "last_check": self.state["last_check"],
            "last_healthy": self.state["last_healthy"],
            "last_restart": self.state["last_restart"],
            "server_pid": self.state.get("server_pid"),
        }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                str(Path(LOGS_DIR) / "health_check.log"),
                encoding="utf-8",
            ),
        ],
    )
    monitor = HealthMonitor()
    monitor.run_forever()


if __name__ == "__main__":
    main()
