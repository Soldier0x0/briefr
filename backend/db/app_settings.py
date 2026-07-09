"""Operator settings persisted in PostgreSQL/SQLite (Phase B).

Keys mirror writable admin config (`config_schema.WRITABLE_CONFIG_KEYS`).
Process environment variables set before startup always win over DB values.
"""

from __future__ import annotations

from db.timeutil import utcnow_str
from db.types import DbConnection

_SELECT_VALUE_SQLITE = "SELECT value FROM app_settings WHERE key = ?"
_SELECT_VALUE_PG = "SELECT value FROM app_settings WHERE key = $1"

_LIST_SQLITE = "SELECT key, value, updated_at FROM app_settings ORDER BY key ASC"
_LIST_PG = "SELECT key, value, updated_at FROM app_settings ORDER BY key ASC"

_UPSERT_SQLITE = """
INSERT INTO app_settings (key, value, updated_at)
VALUES (?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""

_UPSERT_PG = """
INSERT INTO app_settings (key, value, updated_at)
VALUES ($1, $2, $3)
ON CONFLICT(key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def get_app_setting(db: DbConnection, key: str) -> str | None:
    sql = _SELECT_VALUE_PG if _is_postgres_connection(db) else _SELECT_VALUE_SQLITE
    rows = await db.execute_fetchall(sql, (key,))
    return rows[0]["value"] if rows else None


async def set_app_setting(db: DbConnection, key: str, value: str) -> None:
    now = utcnow_str()
    sql = _UPSERT_PG if _is_postgres_connection(db) else _UPSERT_SQLITE
    await db.execute(sql, (key, value, now))


async def list_app_settings(db: DbConnection) -> list[dict]:
    sql = _LIST_PG if _is_postgres_connection(db) else _LIST_SQLITE
    rows = await db.execute_fetchall(sql)
    return [dict(row) for row in rows]
