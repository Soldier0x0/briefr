"""Webhook alert dedupe, delivery log, destinations. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

import json
from typing import Any

from db.dialect import utcnow_str
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
) -> bool:
    pg = _is_postgres_connection(db)
    fields: list[str] = []
    params: list[Any] = []
    pg_n = 1
    if enabled is not None:
        fields.append(f"enabled = {_placeholder(pg, pg_n)}")
        if pg:
            pg_n += 1
        params.append(int(enabled))
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
