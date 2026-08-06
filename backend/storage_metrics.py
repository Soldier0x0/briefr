"""Storage metrics helpers — table sizes, growth estimate, host disk I/O."""

from __future__ import annotations

import pathlib
import re
import time
from typing import Any

_TABLE_SIZES_PG = """
SELECT c.relname AS name,
       pg_total_relation_size(c.oid)::bigint AS size_bytes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
ORDER BY size_bytes DESC
"""

_TABLE_SIZES_SQLITE = """
SELECT name, SUM(pgsize) AS size_bytes
FROM dbstat
GROUP BY name
ORDER BY size_bytes DESC
"""


def _is_postgres_connection(db: Any) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def fetch_table_sizes(db: Any) -> list[dict[str, Any]]:
    sql = _TABLE_SIZES_PG if _is_postgres_connection(db) else _TABLE_SIZES_SQLITE
    try:
        rows = await db.execute_fetchall(sql)
        return [
            {"table": r["name"], "size_bytes": int(r["size_bytes"] or 0)}
            for r in rows
        ]
    except Exception:
        return []


def estimate_growth_bytes_per_day(
    db_size_bytes: int,
    backup_dir: str,
) -> dict[str, Any]:
    """Rough growth estimate from backup archive size trend when available."""
    bdir = pathlib.Path(backup_dir)
    if not bdir.is_dir():
        return {"bytes_per_day": None, "basis": "backup_dir_missing", "sample_days": 0}

    archives: list[tuple[float, int]] = []
    for entry in bdir.iterdir():
        if not entry.is_file():
            continue
        if not (entry.name.endswith(".tar.gz") or entry.name.endswith(".tar.gz.age")):
            continue
        try:
            stat = entry.stat()
            archives.append((stat.st_mtime, stat.st_size))
        except OSError:
            continue

    if len(archives) < 2:
        return {"bytes_per_day": None, "basis": "insufficient_backup_history", "sample_days": 0}

    archives.sort(key=lambda item: item[0])
    oldest_ts, oldest_size = archives[0]
    newest_ts, newest_size = archives[-1]
    day_span = max((newest_ts - oldest_ts) / 86400.0, 1 / 24)
    delta = newest_size - oldest_size
    bytes_per_day = max(0, int(delta / day_span))
    return {
        "bytes_per_day": bytes_per_day,
        "basis": "backup_archive_trend",
        "sample_days": round(day_span, 1),
        "oldest_archive_bytes": oldest_size,
        "newest_archive_bytes": newest_size,
        "current_db_bytes": db_size_bytes,
    }


def _device_for_path(path: str) -> str | None:
    try:
        import subprocess

        result = subprocess.run(
            ["df", "-P", path],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        device = lines[1].split()[0]
        return pathlib.Path(device).name
    except Exception:
        return None


def read_host_disk_io(db_path: str) -> dict[str, Any]:
    """Read cumulative disk I/O from /proc/diskstats when readable."""
    proc_path = pathlib.Path("/proc/diskstats")
    if not proc_path.is_file():
        return {"available": False, "reason": "proc_unavailable"}

    device = _device_for_path(db_path) or ""
    base_device = re.sub(r"\d+$", "", device) if device else ""

    try:
        lines = proc_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {"available": False, "reason": "proc_unreadable"}

    match: list[str] | None = None
    for line in lines:
        parts = line.split()
        if len(parts) < 14:
            continue
        dev_name = parts[2]
        if dev_name == device or (base_device and dev_name == base_device):
            match = parts
            break

    if not match:
        return {"available": False, "reason": "device_not_found", "device": device or None}

    reads = int(match[3])
    read_sectors = int(match[5])
    writes = int(match[7])
    write_sectors = int(match[9])
    sector_bytes = 512
    return {
        "available": True,
        "device": match[2],
        "reads_completed": reads,
        "writes_completed": writes,
        "read_bytes": read_sectors * sector_bytes,
        "write_bytes": write_sectors * sector_bytes,
        "cumulative_since_boot": True,
        "sampled_at": int(time.time()),
    }
