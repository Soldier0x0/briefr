"""Per-user IOC watchlist (V1.5 Theme 4b)."""

from __future__ import annotations

from db.timeutil import utcnow_str
from db.types import DbConnection

_VALID_TYPES = frozenset({"ip", "hash", "domain"})


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def validate_ioc_type(ioc_type: str) -> str:
    t = (ioc_type or "").strip().lower()
    if t not in _VALID_TYPES:
        raise ValueError("type must be ip, hash, or domain")
    return t


async def list_ioc_watchlist(db: DbConnection, user_id: int) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT id, user_id, ioc_type, ioc_value, label, created_at
        FROM ioc_watchlist
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    return [dict(row) for row in rows]


async def upsert_ioc_watchlist_entry(
    db: DbConnection,
    user_id: int,
    ioc_type: str,
    ioc_value: str,
    *,
    label: str = "",
) -> dict:
    ioc_type = validate_ioc_type(ioc_type)
    value = (ioc_value or "").strip()
    if not value or len(value) > 512:
        raise ValueError("ioc value required (max 512 chars)")

    now = utcnow_str()
    if _is_postgres_connection(db):
        await db.execute(
            """
            INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value, label, created_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT(user_id, ioc_type, ioc_value) DO UPDATE SET
                label = excluded.label
            """,
            (user_id, ioc_type, value, label[:200], now),
        )
    else:
        await db.execute(
            """
            INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value, label, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ioc_type, ioc_value) DO UPDATE SET
                label = excluded.label
            """,
            (user_id, ioc_type, value, label[:200], now),
        )

    rows = await db.execute_fetchall(
        """
        SELECT id, user_id, ioc_type, ioc_value, label, created_at
        FROM ioc_watchlist
        WHERE user_id = ? AND ioc_type = ? AND ioc_value = ?
        """,
        (user_id, ioc_type, value),
    )
    return dict(rows[0])


async def delete_ioc_watchlist_entry(
    db: DbConnection,
    user_id: int,
    entry_id: int,
) -> bool:
    if _is_postgres_connection(db):
        cursor = await db.execute(
            "DELETE FROM ioc_watchlist WHERE id = $1 AND user_id = $2",
            (entry_id, user_id),
        )
    else:
        cursor = await db.execute(
            "DELETE FROM ioc_watchlist WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
    return cursor.rowcount > 0
