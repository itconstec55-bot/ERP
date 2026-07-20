"""
Monitoring: System metrics for CPU, Memory, Disk, Network, and Process health.
"""
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("monitoring")

BASE_DIR = Path(__file__).resolve().parent.parent
METRICS_FILE = BASE_DIR / "deployment" / "metrics_history.json"
MAX_HISTORY = 1440  # 24 hours at 1-minute intervals


def get_cpu_percent():
    """Get CPU usage percentage (cross-platform)."""
    try:
        if sys.platform == "win32":
            import psutil
            return psutil.cpu_percent(interval=0.5)
        else:
            import psutil
            return psutil.cpu_percent(interval=0.5)
    except ImportError:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["wmic", "cpu", "get", "loadpercentage"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    val = line.strip()
                    if val and val.lower() != "loadpercentage":
                        try:
                            return float(val)
                        except ValueError:
                            pass
            else:
                result = subprocess.run(
                    ["top", "-bn1"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "%Cpu(s)" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if "id" in p and p.endswith(","):
                                return 100.0 - float(parts[i-1])
        except Exception as e:
            logger.debug(f"get_cpu_percent fallback failed: {e}")
        return 0.0


def get_memory_info():
    """Get memory usage info."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_mb": mem.total // (1024 * 1024),
            "available_mb": mem.available // (1024 * 1024),
            "used_mb": mem.used // (1024 * 1024),
            "percent": mem.percent,
            "swap_total_mb": psutil.swap_memory().total // (1024 * 1024),
            "swap_used_mb": psutil.swap_memory().used // (1024 * 1024),
            "swap_percent": psutil.swap_memory().percent,
        }
    except ImportError:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
                # Header line maps column -> index
                header = None
                for line in lines:
                    if "TotalVisibleMemorySize" in line or "FreePhysicalMemory" in line:
                        tokens = line.split()
                        header = {t: i for i, t in enumerate(tokens)}
                        break
                if header and "FreePhysicalMemory" in header and "TotalVisibleMemorySize" in header:
                    for line in lines:
                        if line == " ".join(list(header.keys())):
                            continue
                        parts = line.split()
                        if len(parts) >= max(header.values()) + 1:
                            try:
                                total_kb = float(parts[header["TotalVisibleMemorySize"]])
                                free_kb = float(parts[header["FreePhysicalMemory"]])
                                used_kb = total_kb - free_kb
                                return {
                                    "total_mb": int(total_kb // 1024),
                                    "available_mb": int(free_kb // 1024),
                                    "used_mb": int(used_kb // 1024),
                                    "percent": round((used_kb / total_kb) * 100, 1),
                                }
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            logger.debug(f"get_memory_info fallback failed: {e}")
    return {"total_mb": 0, "available_mb": 0, "used_mb": 0, "percent": 0}


def get_disk_info():
    """Get disk usage info for the project drive."""
    try:
        usage = shutil.disk_usage(str(BASE_DIR))
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round((usage.used / usage.total) * 100, 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def get_process_info():
    """Get Django/ Python process info."""
    try:
        import psutil
        current_pid = os.getpid()
        proc = psutil.Process(current_pid)
        with proc.oneshot():
            return {
                "pid": current_pid,
                "cpu_percent": proc.cpu_percent(interval=0.3),
                "memory_mb": proc.memory_info().rss // (1024 * 1024),
                "threads": proc.num_threads(),
                "open_files": len(proc.open_files()),
                "connections": len(proc.connections()),
                "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
            }
    except ImportError:
        return {"pid": os.getpid(), "note": "psutil not installed"}
    except Exception as e:
        return {"pid": os.getpid(), "error": str(e)}


def get_uptime():
    """Get system uptime."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["wmic", "OS", "get", "LastBootUpTime"],
                capture_output=True, text=True, timeout=5
            )
            lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            for line in lines:
                if line.lower().startswith("lastbootuptime"):
                    continue
                boot_str = line.split(".")[0]
                try:
                    boot_time = datetime.strptime(boot_str, "%Y%m%d%H%M%S")
                    uptime = datetime.now() - boot_time
                    days = uptime.days
                    hours = uptime.seconds // 3600
                    minutes = (uptime.seconds % 3600) // 60
                    return f"{days} يوم {hours:02d}:{minutes:02d}"
                except ValueError:
                    pass
        else:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return f"{days} يوم {hours:02d}:{minutes:02d}"
    except Exception as e:
        logger.debug(f"get_uptime failed: {e}")
    return "غير متاح"


def get_network_info():
    """Get network I/O info."""
    try:
        import psutil
        net = psutil.net_io_counters()
        return {
            "bytes_sent_mb": round(net.bytes_sent / (1024 * 1024), 1),
            "bytes_recv_mb": round(net.bytes_recv / (1024 * 1024), 1),
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        }
    except ImportError:
        return {}
    except Exception:
        return {}


def get_db_size():
    """Get database file size."""
    db_path = BASE_DIR / "db.sqlite3"
    pg_size = None
    try:
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            return {"engine": "sqlite", "size_mb": round(size_mb, 1)}
    except Exception:
        pass
    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "accounting_system.settings")
        django.setup()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            row = cursor.fetchone()
            if row:
                pg_size = round(row[0] / (1024 * 1024), 1)
        if pg_size:
            return {"engine": "postgresql", "size_mb": pg_size}
    except Exception:
        pass
    return {"engine": "unknown", "size_mb": 0}


def get_all_metrics():
    """Collect all system metrics at once."""
    return {
        "timestamp": datetime.now().isoformat(),
        "hostname": platform.node(),
        "platform": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split()[0],
        "cpu": {
            "percent": get_cpu_percent(),
            "cores_physical": os.cpu_count() or 0,
            "cores_logical": os.cpu_count() or 0,
        },
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "process": get_process_info(),
        "uptime": get_uptime(),
        "network": get_network_info(),
        "database": get_db_size(),
    }


def save_metrics_history(metrics):
    """Append metrics to history file for charting."""
    try:
        history = []
        if METRICS_FILE.exists():
            history = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        # Keep only CPU, memory, disk percent for charting
        record = {
            "t": metrics["timestamp"],
            "cpu": metrics["cpu"]["percent"],
            "mem": metrics["memory"]["percent"],
            "disk": metrics["disk"]["percent"],
        }
        history.append(record)
        # Trim to max history
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        METRICS_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save metrics history: {e}")


def get_metrics_history(hours=1):
    """Get metrics history for charting (last N hours)."""
    try:
        if not METRICS_FILE.exists():
            return []
        history = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        return [r for r in history if r.get("t", "") >= cutoff]
    except Exception:
        return []


def get_service_status():
    """Get deployment service status summary."""
    state_file = BASE_DIR / "deployment" / "health_state.json"
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "consecutive_failures": state.get("consecutive_failures", 0),
        "total_restarts": state.get("total_restarts", 0),
        "last_healthy": state.get("last_healthy"),
        "last_restart": state.get("last_restart"),
        "last_check": state.get("last_check"),
    }


if __name__ == "__main__":
    import json
    metrics = get_all_metrics()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
