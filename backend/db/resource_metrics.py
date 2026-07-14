"""Resource utilization samples — storage and retention (RB-1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from db.types import DbConnection

RESOURCE_METRICS_RETENTION_DAYS = 30

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

_PG_STAT_SNAPSHOT_PG = """
SELECT xact_commit,
       xact_rollback,
       blks_read,
       blks_hit,
       pg_database_size(current_database()) AS db_size_bytes
FROM pg_stat_database
WHERE datname = current_database()
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
    retention_days: int = RESOURCE_METRICS_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_iso(retention_days)
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
