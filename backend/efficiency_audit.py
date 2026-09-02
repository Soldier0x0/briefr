"""Live efficiency audit — subsystem footprint and operator recommendations (Phase C)."""

from __future__ import annotations

import os
import pathlib
from datetime import datetime, timezone
from typing import Any

from db.connection import get_pool_stats
from db.types import DbConnection
from host_profile import collect_host_profile
from storage_metrics import fetch_table_sizes

_BYTES_500_MB = 500 * 1024 * 1024
_BYTES_1_GB = 1024 * 1024 * 1024


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _table_bytes(
    table_sizes: list[dict[str, Any]],
    name: str,
    *,
    schema: str | None = None,
) -> int:
    matches = [row for row in table_sizes if row.get("table") == name]
    if schema is not None:
        matches = [row for row in matches if row.get("schema") == schema]
    elif any(row.get("schema") in ("app", "intel") for row in matches):
        matches = [row for row in matches if row.get("schema") in ("app", "intel")]
    return sum(int(row.get("size_bytes") or 0) for row in matches)


async def _row_count(db: DbConnection, table: str) -> int:
    try:
        rows = await db.execute_fetchall(f"SELECT COUNT(*) AS cnt FROM {table}")
        return int(rows[0]["cnt"]) if rows else 0
    except Exception:
        return 0


async def _api_events_per_day(db: DbConnection) -> int:
    try:
        rows = await db.execute_fetchall(
            """
            SELECT COUNT(*)::int AS cnt
            FROM api_call_events
            WHERE ts >= NOW() - INTERVAL '24 hours'
            """
        )
        return int(rows[0]["cnt"]) if rows else 0
    except Exception:
        return 0


def _backup_archive_stats(backup_dir: str) -> tuple[int, int]:
    bdir = pathlib.Path(backup_dir)
    if not bdir.is_dir():
        return 0, 0
    count = 0
    total_bytes = 0
    for entry in bdir.iterdir():
        if not entry.is_file():
            continue
        if not (entry.name.endswith(".tar.gz") or entry.name.endswith(".tar.gz.age")):
            continue
        try:
            total_bytes += entry.stat().st_size
            count += 1
        except OSError:
            continue
    return count, total_bytes


def _pct_of(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return round(part / whole * 100, 2)


def _rec_detail(
    *,
    basis: str,
    confidence: str,
    impact_risk: str,
    reversible: bool,
) -> dict[str, Any]:
    """Operator-facing metadata for efficiency suggestions."""
    return {
        "basis": basis,
        "confidence": confidence,
        "impact_risk": impact_risk,
        "reversible": reversible,
        "auto_scalable": False,
    }


async def build_efficiency_report(
    db: DbConnection,
    *,
    db_path: str = "",
    backup_dir: str | None = None,
) -> dict[str, Any]:
    """Return subsystem breakdown and actionable recommendations."""
    resolved_backup_dir = backup_dir or os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
    host_profile = collect_host_profile(db_path="postgresql")
    table_sizes = await fetch_table_sizes(db)
    size_by_table = {row["table"]: int(row["size_bytes"] or 0) for row in table_sizes}

    api_bytes = _table_bytes(table_sizes, "api_call_events")
    feed_cache_bytes = _table_bytes(table_sizes, "feed_cache")
    ioc_cache_bytes = _table_bytes(table_sizes, "ioc_cache")
    db_size_bytes = sum(size_by_table.values()) if size_by_table else 0
    # Get DB size from pg_database_size
    if db_size_bytes <= 0:
        try:
            rows = await db.execute_fetchall(
                "SELECT pg_database_size(current_database()) as size"
            )
            db_size_bytes = int(rows[0]["size"]) if rows else 0
        except Exception:
            db_size_bytes = 0

    archive_count, backup_bytes = _backup_archive_stats(resolved_backup_dir)
    pool_stats = get_pool_stats() or {}
    resource_metrics_rows = await _row_count(db, "resource_metrics")
    feed_cache_rows = await _row_count(db, "feed_cache")
    ioc_cache_rows = await _row_count(db, "ioc_cache")
    api_rows = await _row_count(db, "api_call_events")
    api_rpd = await _api_events_per_day(db)

    disk_total = int(host_profile.get("disk_total_bytes") or 0)
    mem_total = int(host_profile.get("memory_total_bytes") or 0)

    subsystems: list[dict[str, Any]] = [
        {
            "id": "api_call_events",
            "label": "API call events",
            "bytes": api_bytes,
            "rows": api_rows,
            "requests_per_day": api_rpd,
            "pct_of_disk": _pct_of(api_bytes, disk_total),
            "pct_of_ram": None,
        },
        {
            "id": "feed_cache",
            "label": "Feed cache",
            "bytes": feed_cache_bytes,
            "rows": feed_cache_rows,
            "requests_per_day": None,
            "pct_of_disk": _pct_of(feed_cache_bytes, disk_total),
            "pct_of_ram": None,
        },
        {
            "id": "ioc_cache",
            "label": "IOC cache",
            "bytes": ioc_cache_bytes,
            "rows": ioc_cache_rows,
            "requests_per_day": None,
            "pct_of_disk": _pct_of(ioc_cache_bytes, disk_total),
            "pct_of_ram": None,
        },
        {
            "id": "resource_metrics",
            "label": "Resource metrics samples",
            "bytes": _table_bytes(table_sizes, "resource_metrics"),
            "rows": resource_metrics_rows,
            "requests_per_day": None,
            "pct_of_disk": _pct_of(_table_bytes(table_sizes, "resource_metrics"), disk_total),
            "pct_of_ram": None,
        },
        {
            "id": "database",
            "label": "Database (all tables)",
            "bytes": db_size_bytes,
            "rows": None,
            "requests_per_day": None,
            "pct_of_disk": _pct_of(db_size_bytes, disk_total),
            "pct_of_ram": None,
        },
        {
            "id": "backups",
            "label": "Backup archives",
            "bytes": backup_bytes,
            "rows": archive_count,
            "requests_per_day": None,
            "pct_of_disk": _pct_of(backup_bytes, disk_total),
            "pct_of_ram": None,
        },
    ]

    if pool_stats:
        subsystems.append({
            "id": "connection_pool",
            "label": "Connection pool",
            "bytes": None,
            "rows": pool_stats.get("in_use"),
            "requests_per_day": None,
            "pct_of_disk": None,
            "pct_of_ram": None,
            "pool_size": pool_stats.get("max") or pool_stats.get("size"),
            "pool_idle": pool_stats.get("idle"),
        })

    recommendations = _build_recommendations(
        host_profile=host_profile,
        api_bytes=api_bytes,
        api_rpd=api_rpd,
        archive_count=archive_count,
        pool_stats=pool_stats,
        resource_metrics_rows=resource_metrics_rows,
        mem_total=mem_total,
        disk_total=disk_total,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_profile": host_profile,
        "subsystems": subsystems,
        "recommendations": recommendations,
    }


def _build_recommendations(
    *,
    host_profile: dict[str, Any],
    api_bytes: int,
    api_rpd: int,
    archive_count: int,
    pool_stats: dict[str, Any],
    resource_metrics_rows: int,
    mem_total: int,
    disk_total: int,
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    disk_used = int(host_profile.get("disk_used_bytes") or 0)
    disk_pct = (disk_used / disk_total * 100) if disk_total > 0 else 0

    if api_bytes > _BYTES_500_MB and _env_bool("API_CALL_EVENTS_ENABLED", default=True):
        est_saved = max(api_bytes // 2, _BYTES_500_MB // 2)
        recs.append({
            "id": "api_events_volume",
            "severity": "warn",
            "title": "API call event log is large",
            "description": (
                "Outbound API metering stores every request in api_call_events. "
                "Disable metering if you do not need the audit trail, or rely on shorter retention."
            ),
            "config_key": "API_CALL_EVENTS_ENABLED",
            "current_value": os.environ.get("API_CALL_EVENTS_ENABLED", "1"),
            "suggested_value": "0",
            "estimated_savings": {"bytes": est_saved, "requests_per_day": api_rpd},
            **_rec_detail(
                basis=(
                    f"api_call_events table is {api_bytes / (1024 * 1024):.0f} MB "
                    f"with ~{api_rpd:,} events in the last 24h."
                ),
                confidence="high",
                impact_risk=(
                    "Disabling API_CALL_EVENTS stops new metering rows and hides per-key "
                    "usage history in Admin → API Keys. Live CVE feeds and IOC lookups are unaffected."
                ),
                reversible=True,
            ),
        })

    retention = _env_int("BACKUP_RETENTION_COUNT", 30)
    if archive_count > 50 and disk_pct > 70:
        recs.append({
            "id": "backup_retention",
            "severity": "warn",
            "title": "Many backup archives on a full disk",
            "description": (
                f"{archive_count} backup archives on a partition at {disk_pct:.0f}% used. "
                "Lowering retention frees disk without affecting live data."
            ),
            "config_key": "BACKUP_RETENTION_COUNT",
            "current_value": str(retention),
            "suggested_value": "30",
            "estimated_savings": {"bytes": max(0, (archive_count - 30) * (disk_used // max(archive_count, 1)))},
            **_rec_detail(
                basis=f"{archive_count} archives on disk at {disk_pct:.0f}% capacity (psutil).",
                confidence="medium",
                impact_risk=(
                    "Lowering BACKUP_RETENTION_COUNT deletes oldest archives on the next backup run. "
                    "You lose restore points beyond the new limit; live DB and feeds are unaffected."
                ),
                reversible=True,
            ),
        })

    sample_interval = _env_int("RESOURCE_SAMPLE_INTERVAL_SECONDS", 60)
    if sample_interval < 120 and resource_metrics_rows > 500:
        daily_writes = int(86400 / max(sample_interval, 1))
        saved_writes = daily_writes - int(86400 / 120)
        recs.append({
            "id": "sample_interval",
            "severity": "info",
            "title": "Resource collector interval is aggressive",
            "description": (
                f"Sampling every {sample_interval}s writes ~{daily_writes:,} resource_metrics rows/day. "
                "120s still gives useful charts with fewer writes."
            ),
            "config_key": "RESOURCE_SAMPLE_INTERVAL_SECONDS",
            "current_value": str(sample_interval),
            "suggested_value": "120",
            "estimated_savings": {"rows": saved_writes * 30},
            **_rec_detail(
                basis=(
                    f"RESOURCE_SAMPLE_INTERVAL_SECONDS={sample_interval} and "
                    f"{resource_metrics_rows:,} resource_metrics rows on disk."
                ),
                confidence="high",
                impact_risk=(
                    "Admin Resources charts update less frequently (120s vs current interval). "
                    "No impact on CVE ingest, detection, or API traffic."
                ),
                reversible=True,
            ),
        })

    from feeds.otx_continuous import get_otx_continuous_budget_per_run, otx_continuous_enabled

    if otx_continuous_enabled() and api_rpd > 5000:
        current_budget = get_otx_continuous_budget_per_run()
        suggested = max(50, current_budget // 2)
        recs.append({
            "id": "otx_budget",
            "severity": "info",
            "title": "High OTX continuous API volume",
            "description": (
                f"OTX continuous sync is enabled with budget {current_budget}/run and "
                f"~{api_rpd:,} API events/day. Lower the per-run budget to reduce outbound calls."
            ),
            "config_key": "OTX_CONTINUOUS_BUDGET_PER_RUN",
            "current_value": str(current_budget),
            "suggested_value": str(suggested),
            "estimated_savings": {"requests_per_day": max(0, api_rpd // 4)},
            **_rec_detail(
                basis=(
                    f"OTX continuous enabled, budget {current_budget}/run, "
                    f"~{api_rpd:,} api_call_events in 24h."
                ),
                confidence="medium",
                impact_risk=(
                    "Fewer OTX pulses per scheduler run — campaign correlation may lag on "
                    "high-churn threat feeds. Ingest and NVD sync are unaffected."
                ),
                reversible=True,
            ),
        })

    pool_size = _env_int("DATABASE_POOL_SIZE", 10)
    in_use = int(pool_stats.get("in_use") or 0) if pool_stats else 0
    pool_max = int(pool_stats.get("max") or pool_stats.get("size") or pool_size) if pool_stats else pool_size
    if pool_max > 5 and in_use > 0 and in_use < pool_max // 3:
        suggested_pool = max(3, in_use + 2)
        if suggested_pool < pool_size:
            recs.append({
                "id": "pool_rightsize",
                "severity": "info",
                "title": "Connection pool may be oversized",
                "description": (
                    f"Pool max {pool_max} but typical in-use is {in_use}. "
                    f"Rightsizing to {suggested_pool} reduces idle Postgres connections."
                ),
                "config_key": "DATABASE_POOL_SIZE",
                "current_value": str(pool_size),
                "suggested_value": str(suggested_pool),
                "estimated_savings": {},
                **_rec_detail(
                    basis=f"Pool snapshot: {in_use} in use of max {pool_max} (asyncpg counters).",
                    confidence="low",
                    impact_risk=(
                        "Under heavy concurrent load, a smaller pool can queue requests. "
                        "Only apply if peak usage stays well below the suggested size."
                    ),
                    reversible=True,
                ),
            })

    metrics_retention = _env_int("RESOURCE_METRICS_RETENTION_DAYS", 30)
    if resource_metrics_rows > 10_000 and metrics_retention > 14:
        recs.append({
            "id": "metrics_retention",
            "severity": "info",
            "title": "Resource metrics retention could be shortened",
            "description": (
                f"{resource_metrics_rows:,} resource_metrics rows retained for {metrics_retention} days. "
                "14 days is enough for admin charts while reducing table size."
            ),
            "config_key": "RESOURCE_METRICS_RETENTION_DAYS",
            "current_value": str(metrics_retention),
            "suggested_value": "14",
            "estimated_savings": {"rows": resource_metrics_rows // 2},
            **_rec_detail(
                basis=f"{resource_metrics_rows:,} resource_metrics rows; retention {metrics_retention} days.",
                confidence="high",
                impact_risk=(
                    "Admin Resources history older than 14 days is pruned on the next retention job. "
                    "Live monitoring and alerts are unaffected."
                ),
                reversible=True,
            ),
        })

    if mem_total > 0:
        mem_avail = int(host_profile.get("memory_available_bytes") or 0)
        mem_used_pct = (mem_total - mem_avail) / mem_total * 100
        if mem_used_pct > 85 and api_bytes > _BYTES_1_GB:
            recs.append({
                "id": "memory_pressure",
                "severity": "warn",
                "title": "Host memory pressure with large metering table",
                "description": (
                    f"Host memory is {mem_used_pct:.0f}% used. Large on-disk tables increase cache pressure — "
                    "review API event logging and cache retention."
                ),
                "config_key": None,
                "current_value": None,
                "suggested_value": None,
                "estimated_savings": {},
                **_rec_detail(
                    basis=(
                        f"psutil reports {mem_used_pct:.0f}% RAM used; "
                        f"api_call_events is {api_bytes / (1024 * 1024):.0f} MB."
                    ),
                    confidence="medium",
                    impact_risk=(
                        "Informational only — no one-click apply. Review linked recommendations "
                        "(metering, retention) before changing config."
                    ),
                    reversible=True,
                ),
            })

    return recs
