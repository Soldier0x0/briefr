"""Database health metrics and disk projection for admin Database page (Phase C)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from db.integrity import run_integrity_check
from db.types import DbConnection


def project_disk_usage(
    samples: list[dict[str, Any]],
    *,
    horizon_days: int = 30,
    partition_total_bytes: int = 0,
) -> dict[str, Any]:
    """Linear regression on db size samples; returns projection severity."""
    points: list[tuple[float, float]] = []
    for row in samples:
        ts_raw = row.get("ts")
        size = row.get("db_bytes")
        if ts_raw is None or size is None:
            continue
        try:
            if isinstance(ts_raw, str):
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            else:
                ts = ts_raw
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            points.append((ts.timestamp(), float(size)))
        except (TypeError, ValueError):
            continue

    if len(points) < 2:
        return {
            "projected_bytes": None,
            "daily_growth_bytes": None,
            "pct_of_partition": None,
            "severity": "ok",
            "sample_count": len(points),
        }

    points.sort(key=lambda p: p[0])
    t0, s0 = points[0]
    t1, s1 = points[-1]
    day_span = max((t1 - t0) / 86400.0, 1 / 24)
    daily_growth = (s1 - s0) / day_span
    current = s1
    projected = max(0, current + daily_growth * horizon_days)

    pct_of_partition = None
    severity = "ok"
    if partition_total_bytes > 0:
        pct_of_partition = round(projected / partition_total_bytes * 100, 2)
        if pct_of_partition >= 90:
            severity = "critical"
        elif pct_of_partition >= 70:
            severity = "warn"

    return {
        "projected_bytes": int(projected),
        "daily_growth_bytes": int(daily_growth),
        "pct_of_partition": pct_of_partition,
        "severity": severity,
        "sample_count": len(points),
        "horizon_days": horizon_days,
    }


async def _postgres_db_metrics(db: DbConnection) -> dict[str, Any]:
    size_row = await db.execute_fetchall(
        "SELECT pg_database_size(current_database()) AS db_size_bytes"
    )
    db_size_bytes = int(size_row[0]["db_size_bytes"]) if size_row else 0

    stat_row = await db.execute_fetchall(
        """
        SELECT numbackends,
               blks_hit,
               blks_read
        FROM pg_stat_database
        WHERE datname = current_database()
        """
    )
    connections = 0
    cache_hit_ratio = None
    if stat_row:
        connections = int(stat_row[0]["numbackends"] or 0)
        blks_hit = int(stat_row[0]["blks_hit"] or 0)
        blks_read = int(stat_row[0]["blks_read"] or 0)
        total_blks = blks_hit + blks_read
        if total_blks > 0:
            cache_hit_ratio = round(blks_hit / total_blks * 100, 2)

    wal_size_bytes = 0
    try:
        wal_row = await db.execute_fetchall(
            """
            SELECT COALESCE(SUM(size), 0)::bigint AS wal_bytes
            FROM pg_ls_waldir()
            """
        )
        wal_size_bytes = int(wal_row[0]["wal_bytes"]) if wal_row else 0
    except Exception:
        pass

    table_row = await db.execute_fetchall(
        """
        SELECT COUNT(*)::int AS cnt
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        """
    )
    index_row = await db.execute_fetchall(
        """
        SELECT COUNT(*)::int AS cnt
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'i'
        """
    )

    return {
        "connections": connections,
        "db_size_bytes": db_size_bytes,
        "wal_size_bytes": wal_size_bytes,
        "cache_hit_ratio": cache_hit_ratio,
        "table_count": int(table_row[0]["cnt"]) if table_row else 0,
        "index_count": int(index_row[0]["cnt"]) if index_row else 0,
    }


async def _fetch_db_size_samples(db: DbConnection, days: int = 30) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.execute_fetchall(
        """
        SELECT ts, pg_db_size_bytes AS db_bytes
        FROM resource_metrics
        WHERE ts >= $1 AND pg_db_size_bytes IS NOT NULL
        ORDER BY ts ASC
        """,
        (cutoff,),
    )
    if rows:
        return [{"ts": r["ts"], "db_bytes": r["db_bytes"]} for r in rows]
    return []


async def fetch_database_metrics(
    db: DbConnection,
    *,
    db_path: str = "",
    partition_total_bytes: int = 0,
) -> dict[str, Any]:
    """Collect database metrics plus integrity status and disk projection."""
    del db_path
    integrity = await run_integrity_check(db)
    checked_at = datetime.now(timezone.utc).isoformat()
    core = await _postgres_db_metrics(db)

    samples = await _fetch_db_size_samples(db)
    if not samples and core.get("db_size_bytes"):
        samples = [{"ts": checked_at, "db_bytes": core["db_size_bytes"]}]

    disk_projection = project_disk_usage(
        samples,
        partition_total_bytes=partition_total_bytes,
    )

    return {
        **core,
        "integrity_ok": integrity.ok,
        "integrity_checked_at": checked_at,
        "disk_projection": disk_projection,
    }
