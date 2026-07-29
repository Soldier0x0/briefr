"""Live host hardware profile for admin resources (Phase C)."""

from __future__ import annotations

import os
import shutil
import socket
from datetime import datetime, timezone
from typing import Any

import psutil


def collect_host_profile(db_path: str = "") -> dict[str, Any]:
    """Return current host capacity from psutil and the DB data volume."""
    path = os.path.abspath(db_path) if db_path else "."
    disk_dir = os.path.dirname(path) or "."
    vm = psutil.virtual_memory()
    try:
        cpu_percent = float(psutil.cpu_percent(interval=None))
    except Exception:
        cpu_percent = 0.0
    disk_total = 0
    disk_used = 0
    try:
        du = shutil.disk_usage(disk_dir)
        disk_total = du.total
        disk_used = du.used
    except OSError:
        pass
    return {
        "cpu_count": psutil.cpu_count(logical=False) or 1,
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "cpu_percent": round(cpu_percent, 1),
        "memory_total_bytes": vm.total,
        "memory_available_bytes": vm.available,
        "disk_total_bytes": disk_total,
        "disk_used_bytes": disk_used,
        "disk_path": disk_dir,
        "hostname": socket.gethostname(),
        "sampled_at": datetime.now(timezone.utc).isoformat(),
    }
