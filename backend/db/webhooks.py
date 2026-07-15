"""Webhook alert dedupe, delivery log, destinations. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import json
from typing import Any

from db.timeutil import utcnow_str
from db.types import DbConnection

_WEBHOOK_ALERT_ALIASES = {
    "kev_alert": ("kev_alert", "kev_stack"),
    "kev_stack": ("kev_alert", "kev_stack"),
    "backup_failure": ("backup_failure", "backup_deadman"),
    "backup_deadman": ("backup_failure", "backup_deadman"),
}

_INSERT_ALERT_SQLITE = """
INSERT OR IGNORE INTO webhook_alert_log (alert_type, target)
VALUES (?, ?)
"""

_INSERT_ALERT_PG = """
INSERT INTO webhook_alert_log (alert_type, target)
VALUES ($1, $2)
ON CONFLICT (alert_type, target) DO NOTHING
"""

_INSERT_DELIVERY_SQLITE = """
INSERT INTO webhook_delivery_log (
    destination_id, event_type, dedupe_key, status, error
) VALUES (?, ?, ?, ?, ?)
"""

_INSERT_DELIVERY_PG = """
INSERT INTO webhook_delivery_log (
    destination_id, event_type, dedupe_key, status, error
) VALUES ($1, $2, $3, $4, $5)
"""

_LIST_DESTINATIONS_SQL = """
SELECT id, kind, label, enabled, event_types, config_json, source,
       created_at, updated_at
FROM webhook_destinations
ORDER BY id
"""

_COUNT_DESTINATIONS_BY_KIND_SQLITE = """
SELECT COUNT(*) as cnt FROM webhook_destinations WHERE kind = ?
"""

_COUNT_DESTINATIONS_BY_KIND_PG = """
SELECT COUNT(*) as cnt FROM webhook_destinations WHERE kind = $1
"""

_INSERT_DESTINATION_SQLITE = """
INSERT INTO webhook_destinations (
    id, kind, label, enabled, event_types, config_json, source, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, 'db', ?, ?)
"""

_INSERT_DESTINATION_PG = """
INSERT INTO webhook_destinations (
    id, kind, label, enabled, event_types, config_json, source, created_at, updated_at
) VALUES ($1, $2, $3, $4, $5, $6, 'db', $7, $8)
"""

_DELETE_DESTINATION_SQLITE = """
DELETE FROM webhook_destinations WHERE id = ? AND source = 'db'
"""

_DELETE_DESTINATION_PG = """
DELETE FROM webhook_destinations WHERE id = $1 AND source = 'db'
"""

_SELECT_DESTINATION_SOURCE_SQLITE = """
SELECT source FROM webhook_destinations WHERE id = ?
"""

_SELECT_DESTINATION_SOURCE_PG = """
SELECT source FROM webhook_destinations WHERE id = $1
"""

_INSERT_DEST_DEDUPE_SQLITE = """
INSERT OR IGNORE INTO webhook_destination_dedupe (destination_id, event_type, dedupe_key)
VALUES (?, ?, ?)
"""

_INSERT_DEST_DEDUPE_PG = """
INSERT INTO webhook_destination_dedupe (destination_id, event_type, dedupe_key)
VALUES ($1, $2, $3)
ON CONFLICT (destination_id, event_type, dedupe_key) DO NOTHING
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _webhook_alert_types(alert_type: str) -> tuple[str, ...]:
    return _WEBHOOK_ALERT_ALIASES.get(alert_type, (alert_type,))


def _in_placeholders(count: int, *, pg: bool, start: int = 1) -> str:
    if pg:
        return ", ".join(f"${i}" for i in range(start, start + count))
    return ", ".join("?" for _ in range(count))


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


async def was_webhook_alert_sent(db: DbConnection, alert_type: str, target: str) -> bool:
    types = _webhook_alert_types(alert_type)
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(types), pg=pg, start=1)
    target_ph = _placeholder(pg, len(types) + 1)
    rows = await db.execute_fetchall(
        f"""
        SELECT 1 FROM webhook_alert_log
        WHERE alert_type IN ({placeholders}) AND target = {target_ph}
        """,
        (*types, target),
    )
    return bool(rows)


async def record_webhook_alert(db: DbConnection, alert_type: str, target: str) -> None:
    sql = _INSERT_ALERT_PG if _is_postgres_connection(db) else _INSERT_ALERT_SQLITE
    await db.execute(sql, (alert_type, target))


async def clear_webhook_alert(db: DbConnection, alert_type: str, target: str) -> None:
    types = _webhook_alert_types(alert_type)
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(types), pg=pg, start=1)
    target_ph = _placeholder(pg, len(types) + 1)
    await db.execute(
        f"DELETE FROM webhook_alert_log WHERE alert_type IN ({placeholders}) AND target = {target_ph}",
        (*types, target),
    )


async def record_webhook_delivery(
    db: DbConnection,
    *,
    destination_id: str,
    event_type: str,
    dedupe_key: str | None,
    status: str,
    error: str | None,
) -> None:
    sql = _INSERT_DELIVERY_PG if _is_postgres_connection(db) else _INSERT_DELIVERY_SQLITE
    await db.execute(sql, (destination_id, event_type, dedupe_key, status, error))


async def list_webhook_destinations(db: DbConnection) -> list[dict]:
    rows = await db.execute_fetchall(_LIST_DESTINATIONS_SQL)
    return [dict(row) for row in rows]


async def update_webhook_destination(
    db: DbConnection,
    destination_id: str,
    *,
    enabled: bool | None = None,
    event_types: list[str] | None = None,
    label: str | None = None,
    config: dict[str, Any] | None = None,
) -> bool:
    pg = _is_postgres_connection(db)
    fields: list[str] = []
    params: list[Any] = []
    pg_n = 1
    if enabled is not None:
        fields.append(f"enabled = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(enabled if pg else int(enabled))
    if event_types is not None:
        fields.append(f"event_types = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(json.dumps(event_types))
    if label is not None:
        fields.append(f"label = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(label)
    if config is not None:
        fields.append(f"config_json = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(json.dumps(config))
    if not fields:
        return False
    fields.append(f"updated_at = {_placeholder(pg, pg_n)}")
    if pg:
        pg_n += 1
    params.append(utcnow_str())
    params.append(destination_id)
    id_ph = _placeholder(pg, pg_n)
    cursor = await db.execute(
        f"UPDATE webhook_destinations SET {', '.join(fields)} WHERE id = {id_ph}",
        params,
    )
    return cursor.rowcount > 0


async def list_webhook_delivery_log(
    db: DbConnection,
    *,
    destination_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    pg = _is_postgres_connection(db)
    conditions: list[str] = []
    params: list[Any] = []
    pg_n = 1
    if destination_id:
        conditions.append(f"destination_id = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(destination_id)
    if event_type:
        types = _webhook_alert_types(event_type)
        placeholders = _in_placeholders(len(types), pg=pg, start=pg_n if pg else 1)
        if pg:
            pg_n += len(types)
        conditions.append(f"event_type IN ({placeholders})")
        params.extend(types)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM webhook_delivery_log {where}",
        params,
    )
    total = count_row[0]["cnt"] if count_row else 0
    limit_ph = _placeholder(pg, pg_n)
    if pg:
        pg_n += 1
    offset_ph = _placeholder(pg, pg_n)
    rows = await db.execute_fetchall(
        f"""
        SELECT id, destination_id, event_type, dedupe_key, status, error, attempted_at
        FROM webhook_delivery_log
        {where}
        ORDER BY attempted_at DESC, id DESC
        LIMIT {limit_ph} OFFSET {offset_ph}
        """,
        params + [limit, offset],
    )
    return [dict(row) for row in rows], total


async def build_webhook_destination_health(db: DbConnection) -> list[dict[str, Any]]:
    """Per-destination delivery health from webhook_delivery_log (read-path only)."""
    pg = _is_postgres_connection(db)
    if pg:
        latest_sql = """
            SELECT DISTINCT ON (destination_id)
                destination_id, status, error, attempted_at, event_type
            FROM webhook_delivery_log
            ORDER BY destination_id, attempted_at DESC, id DESC
        """
        since_expr = "NOW() - INTERVAL '24 hours'"
        attempted_cutoff_expr = "attempted_at::timestamptz"
    else:
        latest_sql = """
            SELECT d.destination_id, d.status, d.error, d.attempted_at, d.event_type
            FROM webhook_delivery_log d
            INNER JOIN (
                SELECT destination_id, MAX(id) AS max_id
                FROM webhook_delivery_log
                GROUP BY destination_id
            ) latest
              ON d.id = latest.max_id
        """
        since_expr = "datetime('now', '-24 hours')"
        attempted_cutoff_expr = "attempted_at"

    latest_rows = await db.execute_fetchall(latest_sql)
    success_failure_sql = """
        SELECT destination_id,
               MAX(CASE WHEN status = 'ok' THEN attempted_at END) AS last_success_at,
               MAX(CASE WHEN status != 'ok' THEN attempted_at END) AS last_failure_at
        FROM webhook_delivery_log
        GROUP BY destination_id
    """
    counts_sql = f"""
        SELECT destination_id,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_24h,
               SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS failed_24h
        FROM webhook_delivery_log
        WHERE {attempted_cutoff_expr} >= {since_expr}
        GROUP BY destination_id
    """

    success_failure_rows = await db.execute_fetchall(success_failure_sql)
    count_rows = await db.execute_fetchall(counts_sql)

    success_by_dest = {r["destination_id"]: r["last_success_at"] for r in success_failure_rows}
    failure_by_dest = {r["destination_id"]: r["last_failure_at"] for r in success_failure_rows}
    counts_by_dest = {
        r["destination_id"]: {
            "ok_24h": int(r["ok_24h"] or 0),
            "failed_24h": int(r["failed_24h"] or 0),
        }
        for r in count_rows
    }

    from redact import mask_webhook_delivery_error

    out: list[dict[str, Any]] = []
    for row in latest_rows:
        r = dict(row)
        dest_id = r["destination_id"]
        counts = counts_by_dest.get(dest_id, {"ok_24h": 0, "failed_24h": 0})
        out.append({
            "destination_id": dest_id,
            "last_status": r["status"],
            "last_event_type": r["event_type"],
            "last_attempt_at": r["attempted_at"],
            "last_success_at": success_by_dest.get(dest_id),
            "last_failure_at": failure_by_dest.get(dest_id),
            "last_error": mask_webhook_delivery_error(r.get("error")),
            "ok_24h": counts["ok_24h"],
            "failed_24h": counts["failed_24h"],
        })
    return out


async def count_webhook_destinations_by_kind(db: DbConnection, kind: str) -> int:
    sql = _COUNT_DESTINATIONS_BY_KIND_PG if _is_postgres_connection(db) else _COUNT_DESTINATIONS_BY_KIND_SQLITE
    rows = await db.execute_fetchall(sql, (kind,))
    return int(rows[0]["cnt"]) if rows else 0


async def get_webhook_destination_source(db: DbConnection, destination_id: str) -> str | None:
    sql = _SELECT_DESTINATION_SOURCE_PG if _is_postgres_connection(db) else _SELECT_DESTINATION_SOURCE_SQLITE
    rows = await db.execute_fetchall(sql, (destination_id,))
    if not rows:
        return None
    return rows[0]["source"]


async def create_webhook_destination(
    db: DbConnection,
    *,
    destination_id: str,
    kind: str,
    label: str,
    enabled: bool,
    event_types: list[str],
    config: dict[str, Any],
) -> None:
    now = utcnow_str()
    payload = (
        destination_id,
        kind,
        label,
        enabled if _is_postgres_connection(db) else int(enabled),
        json.dumps(event_types),
        json.dumps(config),
        now,
        now,
    )
    sql = _INSERT_DESTINATION_PG if _is_postgres_connection(db) else _INSERT_DESTINATION_SQLITE
    await db.execute(sql, payload)


async def delete_webhook_destination(db: DbConnection, destination_id: str) -> bool:
    sql = _DELETE_DESTINATION_PG if _is_postgres_connection(db) else _DELETE_DESTINATION_SQLITE
    cursor = await db.execute(sql, (destination_id,))
    return cursor.rowcount > 0


async def was_webhook_destination_sent(
    db: DbConnection,
    destination_id: str,
    event_type: str,
    dedupe_key: str,
) -> bool:
    types = _webhook_alert_types(event_type)
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(types), pg=pg, start=1)
    dest_ph = _placeholder(pg, len(types) + 1)
    key_ph = _placeholder(pg, len(types) + 2)
    rows = await db.execute_fetchall(
        f"""
        SELECT 1 FROM webhook_destination_dedupe
        WHERE event_type IN ({placeholders})
          AND destination_id = {dest_ph}
          AND dedupe_key = {key_ph}
        """,
        (*types, destination_id, dedupe_key),
    )
    return bool(rows)


async def record_webhook_destination_sent(
    db: DbConnection,
    destination_id: str,
    event_type: str,
    dedupe_key: str,
) -> None:
    sql = _INSERT_DEST_DEDUPE_PG if _is_postgres_connection(db) else _INSERT_DEST_DEDUPE_SQLITE
    await db.execute(sql, (destination_id, event_type, dedupe_key))


async def clear_webhook_destination_dedupe(
    db: DbConnection,
    event_type: str,
    dedupe_key: str,
) -> None:
    types = _webhook_alert_types(event_type)
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(types), pg=pg, start=1)
    key_ph = _placeholder(pg, len(types) + 1)
    await db.execute(
        f"""
        DELETE FROM webhook_destination_dedupe
        WHERE event_type IN ({placeholders}) AND dedupe_key = {key_ph}
        """,
        (*types, dedupe_key),
    )


async def claim_webhook_destination_sent(
    db: DbConnection,
    destination_id: str,
    event_type: str,
    dedupe_key: str,
) -> bool:
    """Try to insert a dedupe claim (atomic check-and-set).
    Returns True if the claim was successfully written, False if it was already sent."""
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            """
            INSERT INTO webhook_destination_dedupe (destination_id, event_type, dedupe_key)
            VALUES ($1, $2, $3)
            ON CONFLICT (destination_id, event_type, dedupe_key) DO NOTHING
            RETURNING 1
            """,
            (destination_id, event_type, dedupe_key),
        )
        return bool(rows)
    else:
        try:
            await db.execute(
                """
                INSERT INTO webhook_destination_dedupe (destination_id, event_type, dedupe_key)
                VALUES (?, ?, ?)
                """,
                (destination_id, event_type, dedupe_key),
            )
            return True
        except Exception:
            return False


async def clear_webhook_destination_dedupe_for_dest(
    db: DbConnection,
    destination_id: str,
    event_type: str,
    dedupe_key: str,
) -> None:
    """Remove a dedupe claim for a specific destination (used to rollback on delivery failure)."""
    types = _webhook_alert_types(event_type)
    pg = _is_postgres_connection(db)
    placeholders = _in_placeholders(len(types), pg=pg, start=1)
    dest_ph = _placeholder(pg, len(types) + 1)
    key_ph = _placeholder(pg, len(types) + 2)
    await db.execute(
        f"""
        DELETE FROM webhook_destination_dedupe
        WHERE event_type IN ({placeholders})
          AND destination_id = {dest_ph}
          AND dedupe_key = {key_ph}
        """,
        (*types, destination_id, dedupe_key),
    )
