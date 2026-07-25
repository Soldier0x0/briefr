"""Physical retention sweeps for cache and overlay tables (Sprint C3).

Read paths enforce TTL via ``cached_at`` / ``fetched_at`` filters; this module
deletes rows that are past their physical retention window so tables do not
grow without bound.

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.resource_metrics import purge_old_resource_metrics
from db.types import DbConnection
from ttl_constants import HOURS_PER_YEAR

# Physical retention >= read TTL for each key family (hours).
IOC_CACHE_RETENTION_HOURS = 24

FEED_CACHE_PREFIX_RETENTION: tuple[tuple[str, float], ...] = (
    ("ssvc:", HOURS_PER_YEAR),
    ("correlation:v2:", 7 * 24),
    ("correlation:v1:", 7 * 24),
    ("circl:", 168),
    ("circl_miss:", 48),
    ("sploitus:", 168),
    ("llm_products:", 168),
    ("llm_products_raw:", 168),
    ("otx:cve:", 48),
    ("otx:pulse:", 48),
    ("otx:ioc:", 48),
    ("malwarebazaar:", 48),
    ("urlhaus:", 48),
    ("greynoise:", 48),
    ("sigma:", 48),
    ("detection_ctx:", 168),
    ("detection_ctx_llm:", 168),
    ("elastic:", 48),
    ("incident_rss:", 48),
    ("incident_feed:snapshot", 7 * 24),
    ("wallboard:snapshot", 24),
    ("admin_db_integrity", 24),
)
DEFAULT_FEED_CACHE_RETENTION_HOURS = 168

OTX_TABLE_RETENTION_HOURS = 7 * 24
EPSS_HISTORY_RETENTION_DAYS = 90
CVE_CHANGE_HISTORY_RETENTION_DAYS = 90

# Operator append-only tables (C3 follow-up). ai_operations / webhook_delivery_log
# are high-frequency per-event logs — a month is plenty for observability. audit_log
# is compliance-sensitive, so it keeps a conservative year. api_usage is intentionally
# excluded: it is a (service, date_utc) aggregate (~1 row/service/day), effectively
# bounded, and purging it would drop usage history for negligible space.
AI_OPERATIONS_RETENTION_DAYS = 30
AI_OPERATION_PAYLOADS_RETENTION_DAYS = 7
WEBHOOK_DELIVERY_LOG_RETENTION_DAYS = 30
AUDIT_LOG_RETENTION_DAYS = 365

_PURGE_IOC_CACHE_SQLITE = """
DELETE FROM ioc_cache
WHERE cached_at < ?
"""

_PURGE_IOC_CACHE_PG = """
DELETE FROM ioc_cache
WHERE cached_at < $1
"""

_PURGE_FEED_CACHE_PREFIX_SQLITE = """
DELETE FROM feed_cache
WHERE cache_key LIKE ?
  AND cached_at < ?
"""

_PURGE_FEED_CACHE_PREFIX_PG = """
DELETE FROM feed_cache
WHERE cache_key LIKE $1
  AND cached_at < $2
"""

_PURGE_FEED_CACHE_DEFAULT_SQLITE = """
DELETE FROM feed_cache
WHERE cached_at < ?
"""

_PURGE_FEED_CACHE_DEFAULT_PG = """
DELETE FROM feed_cache
WHERE cached_at < $1
"""

_PURGE_EPSS_HISTORY_SQLITE = """
DELETE FROM epss_history
WHERE recorded_date < ?
"""

_PURGE_EPSS_HISTORY_PG = """
DELETE FROM epss_history
WHERE recorded_date < $1
"""

_PURGE_CVE_CHANGE_HISTORY_SQLITE = """
DELETE FROM cve_change_history
WHERE detected_at < ?
"""

_PURGE_CVE_CHANGE_HISTORY_PG = """
DELETE FROM cve_change_history
WHERE detected_at < $1
"""

_PURGE_OTX_CVE_PULSES_SQLITE = """
DELETE FROM otx_cve_pulses
WHERE fetched_at < ?
"""

_PURGE_OTX_CVE_PULSES_PG = """
DELETE FROM otx_cve_pulses
WHERE fetched_at < $1
"""

_PURGE_OTX_PULSE_IOCS_SQLITE = """
DELETE FROM otx_pulse_iocs
WHERE fetched_at < ?
"""

_PURGE_OTX_PULSE_IOCS_PG = """
DELETE FROM otx_pulse_iocs
WHERE fetched_at < $1
"""

_PURGE_AI_OPERATIONS_SQLITE = """
DELETE FROM ai_operations
WHERE started_at < ?
"""

_PURGE_AI_OPERATIONS_PG = """
DELETE FROM ai_operations
WHERE started_at < $1
"""

_PURGE_AI_OPERATION_PAYLOADS_SQLITE = """
DELETE FROM ai_operation_payloads
WHERE created_at < ?
"""

_PURGE_AI_OPERATION_PAYLOADS_PG = """
DELETE FROM ai_operation_payloads
WHERE created_at < $1
"""

_PURGE_WEBHOOK_DELIVERY_LOG_SQLITE = """
DELETE FROM webhook_delivery_log
WHERE attempted_at < ?
"""

_PURGE_WEBHOOK_DELIVERY_LOG_PG = """
DELETE FROM webhook_delivery_log
WHERE attempted_at < $1
"""

# IDEM-D: a webhook dedupe claim is written (committed) *before* delivery, and
# the failure path clears it — so a claim with NO successful delivery-log row is
# one a crashed worker stranded between claim-commit and delivery. Left in place
# it silently suppresses that alert forever. Sweep such rows once they are older
# than a grace window (not mid-flight) but still within the delivery-log
# retention window (so a genuinely-sent claim whose 'ok' log has aged out is
# never removed, which would cause a spurious re-alert).
STRANDED_DEDUPE_GRACE_HOURS = 1

_PURGE_STRANDED_DEDUPE_SQLITE = """
DELETE FROM webhook_destination_dedupe
WHERE recorded_at < ?
  AND recorded_at >= ?
  AND NOT EXISTS (
      SELECT 1 FROM webhook_delivery_log w
      WHERE w.destination_id = webhook_destination_dedupe.destination_id
        AND w.event_type = webhook_destination_dedupe.event_type
        AND w.dedupe_key = webhook_destination_dedupe.dedupe_key
        AND w.status = 'ok'
  )
"""

_PURGE_STRANDED_DEDUPE_PG = """
DELETE FROM webhook_destination_dedupe d
WHERE d.recorded_at < $1
  AND d.recorded_at >= $2
  AND NOT EXISTS (
      SELECT 1 FROM webhook_delivery_log w
      WHERE w.destination_id = d.destination_id
        AND w.event_type = d.event_type
        AND w.dedupe_key = d.dedupe_key
        AND w.status = 'ok'
  )
"""

_PURGE_AUDIT_LOG_SQLITE = """
DELETE FROM audit_log
WHERE created_at < ?
"""

_PURGE_AUDIT_LOG_PG = """
DELETE FROM audit_log
WHERE created_at < $1
"""

_CHANGES_SQLITE = "SELECT changes() AS n"


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _cutoff_datetime_hours_ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%d %H:%M:%S")


def _since_hours_cutoff(hours: float, *, pg: bool) -> object:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    if pg:
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _cutoff_date_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


async def _rows_deleted(db: DbConnection, cursor) -> int:
    rc = cursor.rowcount
    if rc is not None and rc >= 0:
        return rc
    if _is_postgres_connection(db):
        return 0
    row = await db.execute_fetchall(_CHANGES_SQLITE)
    return int(row[0]["n"] or 0)


async def purge_stale_ioc_cache(
    db: DbConnection,
    retention_hours: float = IOC_CACHE_RETENTION_HOURS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_hours)
    sql = _PURGE_IOC_CACHE_PG if _is_postgres_connection(db) else _PURGE_IOC_CACHE_SQLITE
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_stale_feed_cache(db: DbConnection) -> int:
    deleted = 0
    now = datetime.now(timezone.utc)
    prefix_sql = (
        _PURGE_FEED_CACHE_PREFIX_PG
        if _is_postgres_connection(db)
        else _PURGE_FEED_CACHE_PREFIX_SQLITE
    )
    for prefix, hours in FEED_CACHE_PREFIX_RETENTION:
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(prefix_sql, (f"{prefix}%", cutoff))
        deleted += await _rows_deleted(db, cursor)

    long_prefixes = [
        prefix
        for prefix, hours in FEED_CACHE_PREFIX_RETENTION
        if hours > DEFAULT_FEED_CACHE_RETENTION_HOURS
    ]
    default_cutoff = (now - timedelta(hours=DEFAULT_FEED_CACHE_RETENTION_HOURS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    if long_prefixes:
        not_like = " AND ".join(
            f"cache_key NOT LIKE '{prefix}%'" for prefix in long_prefixes
        )
        default_sql = (
            _PURGE_FEED_CACHE_DEFAULT_PG
            if _is_postgres_connection(db)
            else _PURGE_FEED_CACHE_DEFAULT_SQLITE
        )
        cursor = await db.execute(
            f"""
            {default_sql.rstrip()}
              AND {not_like}
            """,
            (default_cutoff,),
        )
    else:
        default_sql = (
            _PURGE_FEED_CACHE_DEFAULT_PG
            if _is_postgres_connection(db)
            else _PURGE_FEED_CACHE_DEFAULT_SQLITE
        )
        cursor = await db.execute(default_sql, (default_cutoff,))
    deleted += await _rows_deleted(db, cursor)
    return deleted


async def purge_old_epss_history(
    db: DbConnection,
    retention_days: int = EPSS_HISTORY_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_date_days_ago(retention_days)
    sql = _PURGE_EPSS_HISTORY_PG if _is_postgres_connection(db) else _PURGE_EPSS_HISTORY_SQLITE
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_old_cve_change_history(
    db: DbConnection,
    retention_days: int = CVE_CHANGE_HISTORY_RETENTION_DAYS,
) -> int:
    pg = _is_postgres_connection(db)
    cutoff = _since_hours_cutoff(retention_days * 24, pg=pg)
    sql = _PURGE_CVE_CHANGE_HISTORY_PG if pg else _PURGE_CVE_CHANGE_HISTORY_SQLITE
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_stale_otx_tables(
    db: DbConnection,
    retention_hours: float = OTX_TABLE_RETENTION_HOURS,
) -> dict[str, int]:
    cutoff = _cutoff_datetime_hours_ago(retention_hours)
    pg = _is_postgres_connection(db)
    cve_sql = _PURGE_OTX_CVE_PULSES_PG if pg else _PURGE_OTX_CVE_PULSES_SQLITE
    pulse_sql = _PURGE_OTX_PULSE_IOCS_PG if pg else _PURGE_OTX_PULSE_IOCS_SQLITE
    cve_cursor = await db.execute(cve_sql, (cutoff,))
    pulse_cursor = await db.execute(pulse_sql, (cutoff,))
    return {
        "otx_cve_pulses": await _rows_deleted(db, cve_cursor),
        "otx_pulse_iocs": await _rows_deleted(db, pulse_cursor),
    }


async def purge_old_ai_operations(
    db: DbConnection,
    retention_days: int = AI_OPERATIONS_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_days * 24)
    sql = (
        _PURGE_AI_OPERATIONS_PG
        if _is_postgres_connection(db)
        else _PURGE_AI_OPERATIONS_SQLITE
    )
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_old_ai_operation_payloads(
    db: DbConnection,
    retention_days: int = AI_OPERATION_PAYLOADS_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_days * 24)
    sql = (
        _PURGE_AI_OPERATION_PAYLOADS_PG
        if _is_postgres_connection(db)
        else _PURGE_AI_OPERATION_PAYLOADS_SQLITE
    )
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_old_webhook_delivery_log(
    db: DbConnection,
    retention_days: int = WEBHOOK_DELIVERY_LOG_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_days * 24)
    sql = (
        _PURGE_WEBHOOK_DELIVERY_LOG_PG
        if _is_postgres_connection(db)
        else _PURGE_WEBHOOK_DELIVERY_LOG_SQLITE
    )
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_old_audit_log(
    db: DbConnection,
    retention_days: int = AUDIT_LOG_RETENTION_DAYS,
) -> int:
    cutoff = _cutoff_datetime_hours_ago(retention_days * 24)
    sql = _PURGE_AUDIT_LOG_PG if _is_postgres_connection(db) else _PURGE_AUDIT_LOG_SQLITE
    cursor = await db.execute(sql, (cutoff,))
    return await _rows_deleted(db, cursor)


async def purge_stranded_webhook_dedupe(
    db: DbConnection,
    grace_hours: float = STRANDED_DEDUPE_GRACE_HOURS,
) -> int:
    """Remove crash-stranded webhook dedupe claims (IDEM-D) — claimed but never
    confirmed by a successful delivery. Bounded to within the delivery-log
    retention window so a legitimately-sent claim is never removed."""
    grace_cutoff = _cutoff_datetime_hours_ago(grace_hours)
    retention_cutoff = _cutoff_datetime_hours_ago(WEBHOOK_DELIVERY_LOG_RETENTION_DAYS * 24)
    sql = (
        _PURGE_STRANDED_DEDUPE_PG
        if _is_postgres_connection(db)
        else _PURGE_STRANDED_DEDUPE_SQLITE
    )
    cursor = await db.execute(sql, (grace_cutoff, retention_cutoff))
    return await _rows_deleted(db, cursor)


API_CALL_EVENTS_RETENTION_DAYS = 30


async def purge_old_api_call_events(
    db: DbConnection,
    retention_days: int = API_CALL_EVENTS_RETENTION_DAYS,
) -> int:
    from db.api_metering import purge_api_call_events

    return await purge_api_call_events(db, retain_days=retention_days)


async def run_retention_cleanup(db: DbConnection) -> dict[str, int]:
    """Sweep stale cache/overlay rows. Caller commits."""
    otx = await purge_stale_otx_tables(db)
    return {
        "ioc_cache": await purge_stale_ioc_cache(db),
        "feed_cache": await purge_stale_feed_cache(db),
        "epss_history": await purge_old_epss_history(db),
        "cve_change_history": await purge_old_cve_change_history(db),
        "ai_operations": await purge_old_ai_operations(db),
        "ai_operation_payloads": await purge_old_ai_operation_payloads(db),
        "webhook_delivery_log": await purge_old_webhook_delivery_log(db),
        "webhook_dedupe_stranded": await purge_stranded_webhook_dedupe(db),
        "audit_log": await purge_old_audit_log(db),
        "api_call_events": await purge_old_api_call_events(db),
        "resource_metrics": await purge_old_resource_metrics(db),
        **otx,
    }
