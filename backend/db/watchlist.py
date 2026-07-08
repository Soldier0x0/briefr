"""Watchlist CRUD. Split from database.py (Phase 3).

Postgres-native (Post-B Phase 1): queries use explicit ``$n`` placeholders on Postgres
and ``?`` on SQLite — no reliance on ``db/dialect.py`` regex translation for this module.
"""

from __future__ import annotations

from db.dialect import utcnow_str
from db.types import DbConnection

_WATCHLIST_ACTIVE_SQLITE = """
    state = 'pin'
    OR (state = 'snooze'
        AND snooze_until IS NOT NULL
        AND datetime(snooze_until) > datetime('now'))
"""

_WATCHLIST_ACTIVE_PG = """
    state = 'pin'
    OR (state = 'snooze'
        AND snooze_until IS NOT NULL
        AND snooze_until::timestamp > (NOW() AT TIME ZONE 'utc'))
"""

_LIST_ENTRIES_SQLITE = f"""
SELECT cve_id, state, snooze_until, created_at
FROM watchlist
WHERE {_WATCHLIST_ACTIVE_SQLITE}
ORDER BY
    CASE state WHEN 'pin' THEN 0 ELSE 1 END,
    created_at DESC
"""

_LIST_ENTRIES_PG = f"""
SELECT cve_id, state, snooze_until, created_at
FROM watchlist
WHERE {_WATCHLIST_ACTIVE_PG}
ORDER BY
    CASE state WHEN 'pin' THEN 0 ELSE 1 END,
    created_at DESC
"""

_UPSERT_SQLITE = """
INSERT INTO watchlist (cve_id, state, snooze_until, created_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(cve_id) DO UPDATE SET
    state = excluded.state,
    snooze_until = excluded.snooze_until,
    created_at = excluded.created_at
"""

_UPSERT_PG = """
INSERT INTO watchlist (cve_id, state, snooze_until, created_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT(cve_id) DO UPDATE SET
    state = excluded.state,
    snooze_until = excluded.snooze_until,
    created_at = excluded.created_at
"""

_SELECT_BY_CVE_SQLITE = (
    "SELECT cve_id, state, snooze_until, created_at FROM watchlist WHERE cve_id = ?"
)
_SELECT_BY_CVE_PG = (
    "SELECT cve_id, state, snooze_until, created_at FROM watchlist WHERE cve_id = $1"
)

_DELETE_SQLITE = "DELETE FROM watchlist WHERE cve_id = ?"
_DELETE_PG = "DELETE FROM watchlist WHERE cve_id = $1"

_DELETE_SNOOZES_SQL = "DELETE FROM watchlist WHERE state = 'snooze'"


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _active_sql(db: DbConnection) -> str:
    return _WATCHLIST_ACTIVE_PG if _is_postgres_connection(db) else _WATCHLIST_ACTIVE_SQLITE


async def list_watchlist_entries(db: DbConnection) -> list[dict]:
    """Return active watchlist rows (pins + unexpired snoozes)."""
    sql = _LIST_ENTRIES_PG if _is_postgres_connection(db) else _LIST_ENTRIES_SQLITE
    rows = await db.execute_fetchall(sql)
    return [dict(row) for row in rows]


async def get_watchlist_entry(db: DbConnection, cve_id: str) -> dict | None:
    """Return one active watchlist row, or None."""
    active = _active_sql(db)
    if _is_postgres_connection(db):
        sql = f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE cve_id = $1 AND ({active})
        """
    else:
        sql = f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE cve_id = ? AND ({active})
        """
    rows = await db.execute_fetchall(sql, (cve_id.upper(),))
    return dict(rows[0]) if rows else None


async def upsert_watchlist_entry(
    db: DbConnection,
    cve_id: str,
    state: str,
    snooze_until: str | None = None,
) -> dict:
    """Insert or replace a watchlist row (caller commits)."""
    key = cve_id.upper()
    upsert_sql = _UPSERT_PG if _is_postgres_connection(db) else _UPSERT_SQLITE
    select_sql = _SELECT_BY_CVE_PG if _is_postgres_connection(db) else _SELECT_BY_CVE_SQLITE
    await db.execute(upsert_sql, (key, state, snooze_until, utcnow_str()))
    rows = await db.execute_fetchall(select_sql, (key,))
    return dict(rows[0])


async def delete_watchlist_entry(db: DbConnection, cve_id: str) -> bool:
    """Remove a watchlist row. Returns True when a row was deleted."""
    sql = _DELETE_PG if _is_postgres_connection(db) else _DELETE_SQLITE
    cursor = await db.execute(sql, (cve_id.upper(),))
    return cursor.rowcount > 0


async def delete_all_snooze_entries(db: DbConnection) -> int:
    """Remove every snoozed watchlist row. Returns rows deleted."""
    cursor = await db.execute(_DELETE_SNOOZES_SQL)
    return cursor.rowcount
