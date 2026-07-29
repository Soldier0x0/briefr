"""Resource utilization samples — storage and retention (RB-1)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from db.types import DbConnection

RESOURCE_METRICS_RETENTION_DAYS = 30


def get_resource_metrics_retention_days() -> int:
    try:
        return max(7, int(os.environ.get("RESOURCE_METRICS_RETENTION_DAYS", str(RESOURCE_METRICS_RETENTION_DAYS))))
    except (TypeError, ValueError):
        return RESOURCE_METRICS_RETENTION_DAYS
RESOURCE_METRICS_MAX_SERIES_POINTS = 500

VALID_RESOURCE_WINDOWS = frozenset({"1d", "3d", "7d", "30d"})
_WINDOW_HOURS = {"1d": 24, "3d": 72, "7d": 168, "30d": 720}

_SUMMARY_METRICS = tuple(col for col in (
    "briefr_cpu_pct",
    "briefr_rss_bytes",
    "briefr_io_read_bps",
    "briefr_io_write_bps",
    "briefr_iops_r",
    "briefr_iops_w",
    "pg_cpu_pct",
    "pg_rss_bytes",
    "pg_iops_r",
    "pg_iops_w",
    "req_count",
    "pg_xact_per_min",
    "pg_blks_read_per_min",
    "pg_cache_hit_pct",
    "pg_db_size_bytes",
    "disk_free_bytes",
    "sys_cpu_pct",
    "sys_mem_pct",
))

_RESOURCE_METRICS_COLUMNS = (
    "ts",
    "briefr_cpu_pct",
    "briefr_rss_bytes",
    "briefr_io_read_bps",
    "briefr_io_write_bps",
    "briefr_iops_r",
    "briefr_iops_w",
    "pg_cpu_pct",
    "pg_rss_bytes",
    "pg_iops_r",
    "pg_iops_w",
    "req_count",
    "pg_xact_per_min",
    "pg_blks_read_per_min",
    "pg_cache_hit_pct",
    "pg_db_size_bytes",
    "disk_free_bytes",
    "sys_cpu_pct",
    "sys_mem_pct",
)

_INSERT_RESOURCE_METRICS_SQLITE = f"""
INSERT INTO resource_metrics ({", ".join(_RESOURCE_METRICS_COLUMNS)})
VALUES ({", ".join("?" for _ in _RESOURCE_METRICS_COLUMNS)})
"""

_INSERT_RESOURCE_METRICS_PG = f"""
INSERT INTO resource_metrics ({", ".join(_RESOURCE_METRICS_COLUMNS)})
VALUES ({", ".join(f"${i}" for i in range(1, len(_RESOURCE_METRICS_COLUMNS) + 1))})
"""

_PURGE_RESOURCE_METRICS_SQLITE = """
DELETE FROM resource_metrics
WHERE ts < ?
"""

_PURGE_RESOURCE_METRICS_PG = """
DELETE FROM resource_metrics
WHERE ts < $1
"""

# pg-only: reads pg_stat_database / pg_database_size
_PG_STAT_SNAPSHOT_PG = """
SELECT xact_commit,
       xact_rollback,
       blks_read,
       blks_hit,
       pg_database_size(current_database()) AS db_size_bytes
FROM pg_stat_database
WHERE datname = current_database()
"""

_FETCH_WINDOW_SQLITE = """
SELECT *
FROM resource_metrics
WHERE ts >= ?
ORDER BY ts ASC
"""

_FETCH_WINDOW_PG = """
SELECT *
FROM resource_metrics
WHERE ts >= $1
ORDER BY ts ASC
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _cutoff_iso(days: int = RESOURCE_METRICS_RETENTION_DAYS) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.isoformat()


async def insert_resource_sample(db: DbConnection, sample: dict[str, Any]) -> None:
    row = tuple(sample.get(col) for col in _RESOURCE_METRICS_COLUMNS)
    sql = _INSERT_RESOURCE_METRICS_PG if _is_postgres_connection(db) else _INSERT_RESOURCE_METRICS_SQLITE
    await db.execute(sql, row)


async def purge_old_resource_metrics(
    db: DbConnection,
    retention_days: int | None = None,
) -> int:
    days = retention_days if retention_days is not None else get_resource_metrics_retention_days()
    cutoff = _cutoff_iso(days)
    sql = _PURGE_RESOURCE_METRICS_PG if _is_postgres_connection(db) else _PURGE_RESOURCE_METRICS_SQLITE
    cursor = await db.execute(sql, (cutoff,))
    if hasattr(cursor, "rowcount") and cursor.rowcount is not None:
        return int(cursor.rowcount)
    return 0


async def fetch_pg_stat_snapshot(db: DbConnection) -> dict[str, int] | None:
    if not _is_postgres_connection(db):
        return None
    rows = await db.execute_fetchall(_PG_STAT_SNAPSHOT_PG)
    if not rows:
        return None
    row = rows[0]
    return {
        "xact_commit": int(row["xact_commit"] or 0),
        "xact_rollback": int(row["xact_rollback"] or 0),
        "blks_read": int(row["blks_read"] or 0),
        "blks_hit": int(row["blks_hit"] or 0),
        "db_size_bytes": int(row["db_size_bytes"] or 0),
    }


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {col: row[col] for col in _RESOURCE_METRICS_COLUMNS if col in row.keys()}


def downsample_series(
    rows: list[dict[str, Any]],
    max_points: int = RESOURCE_METRICS_MAX_SERIES_POINTS,
) -> list[dict[str, Any]]:
    """Bucket-average downsample; preserves one row per bucket (midpoint ts)."""
    if len(rows) <= max_points:
        return rows
    numeric_cols = [c for c in _RESOURCE_METRICS_COLUMNS if c != "ts"]
    out: list[dict[str, Any]] = []
    total = len(rows)
    for i in range(max_points):
        start = int(i * total / max_points)
        end = int((i + 1) * total / max_points)
        bucket = rows[start:end]
        if not bucket:
            continue
        point: dict[str, Any] = {"ts": bucket[len(bucket) // 2]["ts"]}
        for col in numeric_cols:
            vals = [b[col] for b in bucket if b.get(col) is not None]
            point[col] = sum(vals) / len(vals) if vals else None
        out.append(point)
    return out


def summarize_metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    pairs = [(r["ts"], r[field]) for r in rows if r.get(field) is not None]
    if not pairs:
        return {"peak": None, "peak_at": None, "avg": None, "low": None}
    values = [v for _, v in pairs]
    peak = max(values)
    low = min(values)
    peak_at = next(ts for ts, val in pairs if val == peak)
    avg = sum(values) / len(values)
    return {"peak": peak, "peak_at": peak_at, "avg": avg, "low": low}


def _degraded_state(rows: list[dict[str, Any]], *, postgres_backend: bool) -> dict[str, str]:
    if not rows:
        return {"code": "empty", "message": "No samples yet — metrics appear after the collector runs."}
    if not postgres_backend:
        return {
            "code": "sqlite",
            "message": "Postgres SQL metrics unavailable — SQLite dev fallback.",
        }
    has_pg_process = any(r.get("pg_cpu_pct") is not None for r in rows)
    has_pg_sql = any(r.get("pg_xact_per_min") is not None for r in rows)
    if has_pg_sql and not has_pg_process:
        return {
            "code": "remote_pg",
            "message": "Postgres process metrics unavailable (remote/container PG) — SQL stats still collected.",
        }
    return {"code": "ok", "message": ""}


async def fetch_resources_response(db: DbConnection, window: str) -> dict[str, Any]:
    from db.config import is_postgres

    if window not in VALID_RESOURCE_WINDOWS:
        raise ValueError(f"Invalid window {window!r}")

    hours = _WINDOW_HOURS[window]
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sql = _FETCH_WINDOW_PG if _is_postgres_connection(db) else _FETCH_WINDOW_SQLITE
    raw_rows = await db.execute_fetchall(sql, (cutoff,))
    rows = [_row_to_dict(r) for r in raw_rows]
    series = downsample_series(rows)
    summary = {metric: summarize_metric(rows, metric) for metric in _SUMMARY_METRICS}
    degraded = _degraded_state(rows, postgres_backend=is_postgres())
    return {
        "window": window,
        "sample_count": len(rows),
        "series": series,
        "summary": summary,
        "degraded": degraded,
        "postgres_backend": is_postgres(),
    }
