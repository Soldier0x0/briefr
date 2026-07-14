"""Process-tree resource sampling for RB-1 (scheduler-side only)."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from db.config import is_postgres
from db.resource_metrics import fetch_pg_stat_snapshot, insert_resource_sample
from db.types import DbConnection
from metrics.request_counter import read_and_reset_request_count
from settings import settings

logger = logging.getLogger(__name__)

_prev_sample: dict[str, Any] | None = None
_cpu_primed = False


def reset_collector_state_for_tests() -> None:
    global _prev_sample, _cpu_primed
    _prev_sample = None
    _cpu_primed = False


def _briefr_pids() -> set[int]:
    root = psutil.Process(os.getpid())
    pids = {root.pid}
    for child in root.children(recursive=True):
        pids.add(child.pid)
    return pids


def _postgres_pids() -> set[int]:
    pids: set[int] = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "postgres" in name:
                pids.add(int(proc.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return pids


def _prime_cpu_percent(pids: set[int]) -> None:
    global _cpu_primed
    for pid in pids:
        try:
            psutil.Process(pid).cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _cpu_primed = True


def _cpu_times_snapshot(pids: set[int]) -> dict[int, tuple[float, float]]:
    snap: dict[int, tuple[float, float]] = {}
    for pid in pids:
        try:
            times = psutil.Process(pid).cpu_times()
            snap[pid] = (float(times.user), float(times.system))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return snap


def _cpu_pct_from_times(
    curr: dict[int, tuple[float, float]],
    prev: dict[int, tuple[float, float]] | None,
    elapsed_sec: float | None,
) -> float | None:
    if not curr:
        return None
    if prev is None or not elapsed_sec or elapsed_sec <= 0:
        return None
    delta = 0.0
    for pid, (user, system) in curr.items():
        if pid not in prev:
            continue
        pu, ps = prev[pid]
        delta += max(0.0, (user - pu) + (system - ps))
    logical_cpus = psutil.cpu_count() or 1
    return min(100.0, (delta / elapsed_sec) / logical_cpus * 100.0)


def _aggregate_process_metrics(
    pids: set[int],
    *,
    prev_cpu_times: dict[int, tuple[float, float]] | None = None,
    elapsed_sec: float | None = None,
) -> dict[str, float | int | None]:
    global _cpu_primed
    if not _cpu_primed:
        _prime_cpu_percent(pids)

    curr_cpu_times = _cpu_times_snapshot(pids)
    cpu = _cpu_pct_from_times(curr_cpu_times, prev_cpu_times, elapsed_sec)
    if cpu is None:
        # Fallback for first sample in a process: non-blocking psutil aggregate.
        cpu = 0.0
        for pid in pids:
            try:
                cpu += float(psutil.Process(pid).cpu_percent(interval=None) or 0.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    rss = 0
    read_bytes = 0
    write_bytes = 0
    read_count = 0
    write_count = 0
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            cpu += proc.cpu_percent(interval=None)
            rss += int(proc.memory_info().rss)
            try:
                io = proc.io_counters()
                read_bytes += int(io.read_bytes)
                write_bytes += int(io.write_bytes)
                read_count += int(io.read_count)
                write_count += int(io.write_count)
            except (psutil.AccessDenied, AttributeError):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {
        "cpu_pct": cpu,
        "cpu_times": curr_cpu_times,
        "rss_bytes": rss,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "read_count": read_count,
        "write_count": write_count,
    }


def _rate_per_sec(curr: int | float, prev: int | float | None, elapsed_sec: float) -> float | None:
    if prev is None or elapsed_sec <= 0:
        return None
    delta = float(curr) - float(prev)
    if delta < 0:
        return None
    return delta / elapsed_sec


def _pg_derived_rates(
    curr: dict[str, int],
    prev: dict[str, int] | None,
    elapsed_sec: float,
) -> tuple[float | None, float | None, float | None]:
    if prev is None or elapsed_sec <= 0:
        return None, None, None
    xact_delta = (curr["xact_commit"] - prev["xact_commit"]) + (
        curr["xact_rollback"] - prev["xact_rollback"]
    )
    if xact_delta < 0:
        xact_delta = 0
    blks_read_delta = curr["blks_read"] - prev["blks_read"]
    if blks_read_delta < 0:
        blks_read_delta = 0
    blks_hit_delta = curr["blks_hit"] - prev["blks_hit"]
    if blks_hit_delta < 0:
        blks_hit_delta = 0
    minutes = elapsed_sec / 60.0
    xact_per_min = xact_delta / minutes if minutes > 0 else None
    blks_read_per_min = blks_read_delta / minutes if minutes > 0 else None
    denom = blks_hit_delta + blks_read_delta
    cache_hit_pct = (blks_hit_delta / denom * 100.0) if denom > 0 else None
    return xact_per_min, blks_read_per_min, cache_hit_pct


def _data_volume_path() -> str:
    if is_postgres():
        return str(Path(settings.db_path).resolve().parent) if settings.db_path else "/"
    db_path = settings.db_path or os.environ.get("DB_PATH", "briefr.db")
    return str(Path(db_path).resolve().parent)


def _disk_free_bytes() -> int | None:
    try:
        return int(psutil.disk_usage(_data_volume_path()).free)
    except Exception:
        return None


async def collect_and_store_sample(db: DbConnection) -> dict[str, Any]:
    """Sample host/process metrics and persist one row. Caller commits."""
    global _prev_sample

    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    sampled_at = time.time()

    briefr_pids = _briefr_pids()
    pg_pids = _postgres_pids() if is_postgres() else set()

    elapsed = None
    if _prev_sample is not None:
        elapsed = max(sampled_at - float(_prev_sample["sampled_at"]), 0.001)

    briefr_raw = _aggregate_process_metrics(
        briefr_pids,
        prev_cpu_times=(_prev_sample or {}).get("briefr_cpu_times"),
        elapsed_sec=elapsed,
    )
    pg_raw = (
        _aggregate_process_metrics(
            pg_pids,
            prev_cpu_times=(_prev_sample or {}).get("pg_cpu_times"),
            elapsed_sec=elapsed,
        )
        if pg_pids
        else None
    )

    briefr_io_read_bps = _rate_per_sec(
        briefr_raw["read_bytes"],
        (_prev_sample or {}).get("briefr_read_bytes"),
        elapsed or 0,
    )
    briefr_io_write_bps = _rate_per_sec(
        briefr_raw["write_bytes"],
        (_prev_sample or {}).get("briefr_write_bytes"),
        elapsed or 0,
    )
    briefr_iops_r = _rate_per_sec(
        briefr_raw["read_count"],
        (_prev_sample or {}).get("briefr_read_count"),
        elapsed or 0,
    )
    briefr_iops_w = _rate_per_sec(
        briefr_raw["write_count"],
        (_prev_sample or {}).get("briefr_write_count"),
        elapsed or 0,
    )

    pg_cpu_pct = None
    pg_rss_bytes = None
    pg_iops_r = None
    pg_iops_w = None
    if pg_raw is not None:
        pg_cpu_pct = pg_raw["cpu_pct"]
        pg_rss_bytes = pg_raw["rss_bytes"]
        pg_iops_r = _rate_per_sec(
            pg_raw["read_count"],
            (_prev_sample or {}).get("pg_read_count"),
            elapsed or 0,
        )
        pg_iops_w = _rate_per_sec(
            pg_raw["write_count"],
            (_prev_sample or {}).get("pg_write_count"),
            elapsed or 0,
        )

    pg_xact_per_min = None
    pg_blks_read_per_min = None
    pg_cache_hit_pct = None
    pg_db_size_bytes = None
    pg_stat = await fetch_pg_stat_snapshot(db)
    if pg_stat is not None:
        pg_db_size_bytes = pg_stat["db_size_bytes"]
        pg_xact_per_min, pg_blks_read_per_min, pg_cache_hit_pct = _pg_derived_rates(
            pg_stat,
            (_prev_sample or {}).get("pg_stat"),
            elapsed or 0,
        )

    try:
        sys_cpu_pct = float(psutil.cpu_percent(interval=0.05))
        sys_mem_pct = float(psutil.virtual_memory().percent)
    except Exception:
        sys_cpu_pct = None
        sys_mem_pct = None

    sample = {
        "ts": ts,
        "briefr_cpu_pct": briefr_raw["cpu_pct"],
        "briefr_rss_bytes": briefr_raw["rss_bytes"],
        "briefr_io_read_bps": briefr_io_read_bps,
        "briefr_io_write_bps": briefr_io_write_bps,
        "briefr_iops_r": briefr_iops_r,
        "briefr_iops_w": briefr_iops_w,
        "pg_cpu_pct": pg_cpu_pct,
        "pg_rss_bytes": pg_rss_bytes,
        "pg_iops_r": pg_iops_r,
        "pg_iops_w": pg_iops_w,
        "req_count": read_and_reset_request_count(),
        "pg_xact_per_min": pg_xact_per_min,
        "pg_blks_read_per_min": pg_blks_read_per_min,
        "pg_cache_hit_pct": pg_cache_hit_pct,
        "pg_db_size_bytes": pg_db_size_bytes,
        "disk_free_bytes": _disk_free_bytes(),
        "sys_cpu_pct": sys_cpu_pct,
        "sys_mem_pct": sys_mem_pct,
    }
    await insert_resource_sample(db, sample)

    _prev_sample = {
        "sampled_at": sampled_at,
        "briefr_read_bytes": briefr_raw["read_bytes"],
        "briefr_write_bytes": briefr_raw["write_bytes"],
        "briefr_read_count": briefr_raw["read_count"],
        "briefr_write_count": briefr_raw["write_count"],
        "briefr_cpu_times": briefr_raw.get("cpu_times"),
        "pg_read_count": pg_raw["read_count"] if pg_raw else None,
        "pg_write_count": pg_raw["write_count"] if pg_raw else None,
        "pg_cpu_times": pg_raw.get("cpu_times") if pg_raw else None,
        "pg_stat": pg_stat,
    }
    return sample
