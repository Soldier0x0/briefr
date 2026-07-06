"""Watchlist CRUD. Split from database.py (Phase 3)."""

import aiosqlite
from db.dialect import utcnow_str


_WATCHLIST_ACTIVE_SQL = """
    state = 'pin'
    OR (state = 'snooze'
        AND snooze_until IS NOT NULL
        AND datetime(snooze_until) > datetime('now'))
"""

async def list_watchlist_entries(db: aiosqlite.Connection) -> list[dict]:
    """Return active watchlist rows (pins + unexpired snoozes)."""
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE {_WATCHLIST_ACTIVE_SQL}
        ORDER BY
            CASE state WHEN 'pin' THEN 0 ELSE 1 END,
            created_at DESC
        """
    )
    return [dict(row) for row in rows]

async def get_watchlist_entry(
    db: aiosqlite.Connection, cve_id: str
) -> dict | None:
    """Return one active watchlist row, or None."""
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, state, snooze_until, created_at
        FROM watchlist
        WHERE cve_id = ? AND ({_WATCHLIST_ACTIVE_SQL})
        """,
        (cve_id.upper(),),
    )
    return dict(rows[0]) if rows else None

async def upsert_watchlist_entry(
    db: aiosqlite.Connection,
    cve_id: str,
    state: str,
    snooze_until: str | None = None,
) -> dict:
    """Insert or replace a watchlist row (caller commits)."""
    key = cve_id.upper()
    await db.execute(
        """
        INSERT INTO watchlist (cve_id, state, snooze_until, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(cve_id) DO UPDATE SET
            state = excluded.state,
            snooze_until = excluded.snooze_until,
            created_at = excluded.created_at
        """,
        (key, state, snooze_until, utcnow_str()),
    )
    rows = await db.execute_fetchall(
        "SELECT cve_id, state, snooze_until, created_at FROM watchlist WHERE cve_id = ?",
        (key,),
    )
    return dict(rows[0])

async def delete_watchlist_entry(db: aiosqlite.Connection, cve_id: str) -> bool:
    """Remove a watchlist row. Returns True when a row was deleted."""
    cursor = await db.execute(
        "DELETE FROM watchlist WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    return cursor.rowcount > 0

async def delete_all_snooze_entries(db: aiosqlite.Connection) -> int:
    """Remove every snoozed watchlist row. Returns rows deleted."""
    cursor = await db.execute("DELETE FROM watchlist WHERE state = 'snooze'")
    return cursor.rowcount
