"""Webhook alert dedupe, delivery log, destinations. Split from database.py (Phase 3)."""

import json
import aiosqlite
from typing import Any
from db.dialect import utcnow_str


_WEBHOOK_ALERT_ALIASES = {
    "kev_alert": ("kev_alert", "kev_stack"),
    "kev_stack": ("kev_alert", "kev_stack"),
    "backup_failure": ("backup_failure", "backup_deadman"),
    "backup_deadman": ("backup_failure", "backup_deadman"),
}

def _webhook_alert_types(alert_type: str) -> tuple[str, ...]:
    return _WEBHOOK_ALERT_ALIASES.get(alert_type, (alert_type,))

async def was_webhook_alert_sent(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> bool:
    types = _webhook_alert_types(alert_type)
    placeholders = ", ".join("?" for _ in types)
    rows = await db.execute_fetchall(
        f"""
        SELECT 1 FROM webhook_alert_log
        WHERE alert_type IN ({placeholders}) AND target = ?
        """,
        (*types, target),
    )
    return bool(rows)

async def record_webhook_alert(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> None:
    await db.execute(
        """
        INSERT OR IGNORE INTO webhook_alert_log (alert_type, target)
        VALUES (?, ?)
        """,
        (alert_type, target),
    )

async def clear_webhook_alert(
    db: aiosqlite.Connection, alert_type: str, target: str
) -> None:
    types = _webhook_alert_types(alert_type)
    placeholders = ", ".join("?" for _ in types)
    await db.execute(
        f"DELETE FROM webhook_alert_log WHERE alert_type IN ({placeholders}) AND target = ?",
        (*types, target),
    )

async def record_webhook_delivery(
    db: aiosqlite.Connection,
    *,
    destination_id: str,
    event_type: str,
    dedupe_key: str | None,
    status: str,
    error: str | None,
) -> None:
    await db.execute(
        """
        INSERT INTO webhook_delivery_log (
            destination_id, event_type, dedupe_key, status, error
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (destination_id, event_type, dedupe_key, status, error),
    )

async def list_webhook_destinations(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    return await db.execute_fetchall(
        """
        SELECT id, kind, label, enabled, event_types, config_json, source,
               created_at, updated_at
        FROM webhook_destinations
        ORDER BY id
        """
    )

async def update_webhook_destination(
    db: aiosqlite.Connection,
    destination_id: str,
    *,
    enabled: bool | None = None,
    event_types: list[str] | None = None,
    label: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(int(enabled))
    if event_types is not None:
        fields.append("event_types = ?")
        params.append(json.dumps(event_types))
    if label is not None:
        fields.append("label = ?")
        params.append(label)
    if not fields:
        return False
    fields.append("updated_at = ?")
    params.append(utcnow_str())
    params.append(destination_id)
    cursor = await db.execute(
        f"UPDATE webhook_destinations SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    return cursor.rowcount > 0

async def list_webhook_delivery_log(
    db: aiosqlite.Connection,
    *,
    destination_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[aiosqlite.Row], int]:
    conditions: list[str] = []
    params: list[Any] = []
    if destination_id:
        conditions.append("destination_id = ?")
        params.append(destination_id)
    if event_type:
        types = _webhook_alert_types(event_type)
        placeholders = ", ".join("?" for _ in types)
        conditions.append(f"event_type IN ({placeholders})")
        params.extend(types)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM webhook_delivery_log {where}",
        params,
    )
    total = count_row[0]["cnt"] if count_row else 0
    rows = await db.execute_fetchall(
        f"""
        SELECT id, destination_id, event_type, dedupe_key, status, error, attempted_at
        FROM webhook_delivery_log
        {where}
        ORDER BY attempted_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return rows, total
