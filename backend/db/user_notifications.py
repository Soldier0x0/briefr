"""Per-user in-app notifications — analyst watchlist + operator alerts."""

from __future__ import annotations

from typing import Any

from db.timeutil import utcnow_str
from db.types import DbConnection

_SCOPE_ANALYST = "analyst"
_SCOPE_OPERATOR = "operator"

def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _placeholder(pg: bool, index: int) -> str:
    return f"${index}" if pg else "?"


_INSERT_SQLITE = """
INSERT OR IGNORE INTO user_notifications (
    user_id, scope, category, severity, title, body,
    entity_type, entity_id, dedupe_key, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_PG = """
INSERT INTO user_notifications (
    user_id, scope, category, severity, title, body,
    entity_type, entity_id, dedupe_key, created_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (user_id, dedupe_key) DO NOTHING
"""


_MARK_SEEN_SQLITE = """
UPDATE user_notifications
SET read_at = ?
WHERE user_id = ?
  AND scope = ?
  AND dismissed_at IS NULL
  AND read_at IS NULL
"""

_MARK_SEEN_PG = """
UPDATE user_notifications
SET read_at = $3
WHERE user_id = $1
  AND scope = $2
  AND dismissed_at IS NULL
  AND read_at IS NULL
"""

_DISMISS_ONE_SQLITE = """
UPDATE user_notifications
SET dismissed_at = ?, read_at = COALESCE(read_at, ?)
WHERE id = ? AND user_id = ?
  AND dismissed_at IS NULL
"""

_DISMISS_ONE_PG = """
UPDATE user_notifications
SET dismissed_at = $3, read_at = COALESCE(read_at, $4)
WHERE id = $1 AND user_id = $2
  AND dismissed_at IS NULL
"""

_DISMISS_ALL_SQLITE = """
UPDATE user_notifications
SET dismissed_at = ?, read_at = COALESCE(read_at, ?)
WHERE user_id = ?
  AND scope = ?
  AND dismissed_at IS NULL
"""

_DISMISS_ALL_PG = """
UPDATE user_notifications
SET dismissed_at = $3, read_at = COALESCE(read_at, $4)
WHERE user_id = $1
  AND scope = $2
  AND dismissed_at IS NULL
"""


async def list_active_user_ids(db: DbConnection, *, scope: str) -> list[int]:
    if scope == _SCOPE_OPERATOR:
        rows = await db.execute_fetchall(
            "SELECT id FROM users WHERE is_active = 1 AND role = 'admin'"
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT id FROM users WHERE is_active = 1"
        )
    return [int(r["id"]) for r in rows]


async def insert_notification(
    db: DbConnection,
    *,
    user_id: int,
    scope: str,
    category: str,
    severity: str,
    title: str,
    body: str = "",
    entity_type: str = "",
    entity_id: str = "",
    dedupe_key: str,
) -> bool:
    """Insert one notification row. Returns True when a new row was created."""
    sql = _INSERT_PG if _is_postgres_connection(db) else _INSERT_SQLITE
    created_at = utcnow_str()
    result = await db.execute(
        sql,
        (
            user_id,
            scope,
            category,
            severity,
            title,
            body or "",
            entity_type or "",
            entity_id or "",
            dedupe_key,
            created_at,
        ),
    )
    return int(getattr(result, "rowcount", 0) or 0) > 0


async def list_notifications(
    db: DbConnection,
    *,
    user_id: int,
    scope: str,
    limit: int = 30,
    view: str = "inbox",
) -> list[dict[str, Any]]:
    if view not in ("inbox", "done"):
        raise ValueError("view must be inbox or done")
    pg = _is_postgres_connection(db)
    if scope == "all":
        scope_clause = ""
        lim = _placeholder(pg, 2)
        base_params: tuple[Any, ...] = (user_id, max(1, min(limit, 100)))
    else:
        scope_clause = f"AND scope = {_placeholder(pg, 2)}"
        lim = _placeholder(pg, 3)
        base_params = (user_id, scope, max(1, min(limit, 100)))
    if view == "done":
        dismissed_clause = "dismissed_at IS NOT NULL"
        order_by = "datetime(dismissed_at) DESC"
    else:
        dismissed_clause = "dismissed_at IS NULL"
        order_by = "datetime(created_at) DESC"
    rows = await db.execute_fetchall(
        f"""
        SELECT id, scope, category, severity, title, body,
               entity_type, entity_id, dedupe_key, created_at, read_at, dismissed_at
        FROM user_notifications
        WHERE user_id = {_placeholder(pg, 1)}
          {scope_clause}
          AND {dismissed_clause}
        ORDER BY {order_by}
        LIMIT {lim}
        """,
        base_params,
    )
    return [dict(r) for r in rows]


async def count_unread(
    db: DbConnection,
    *,
    user_id: int,
    scope: str,
) -> int:
    pg = _is_postgres_connection(db)
    if scope == "all":
        scope_clause = ""
        params: tuple[Any, ...] = (user_id,)
    else:
        scope_clause = f"AND scope = {_placeholder(pg, 2)}"
        params = (user_id, scope)
    rows = await db.execute_fetchall(
        f"""
        SELECT COUNT(*) AS cnt FROM user_notifications
        WHERE user_id = {_placeholder(pg, 1)}
          {scope_clause}
          AND dismissed_at IS NULL
          AND read_at IS NULL
        """,
        params,
    )
    return int(rows[0]["cnt"]) if rows else 0


async def mark_one_read(
    db: DbConnection,
    *,
    user_id: int,
    notification_id: int,
) -> bool:
    now = utcnow_str()
    pg = _is_postgres_connection(db)
    sql = f"""
        UPDATE user_notifications
        SET read_at = COALESCE(read_at, {_placeholder(pg, 3 if pg else 1)})
        WHERE id = {_placeholder(pg, 1 if pg else 2)}
          AND user_id = {_placeholder(pg, 2 if pg else 3)}
          AND dismissed_at IS NULL
        """
    params = (notification_id, user_id, now) if pg else (now, notification_id, user_id)
    result = await db.execute(sql, params)
    return int(getattr(result, "rowcount", 0) or 0) > 0


async def mark_scope_read(db: DbConnection, *, user_id: int, scope: str) -> int:
    now = utcnow_str()
    pg = _is_postgres_connection(db)
    if scope == "all":
        sql = f"""
            UPDATE user_notifications
            SET read_at = {_placeholder(pg, 2 if pg else 1)}
            WHERE user_id = {_placeholder(pg, 1 if pg else 2)}
              AND dismissed_at IS NULL
              AND read_at IS NULL
            """
        params: tuple[Any, ...] = (user_id, now) if pg else (now, user_id)
    elif pg:
        sql, params = _MARK_SEEN_PG, (user_id, scope, now)
    else:
        sql, params = _MARK_SEEN_SQLITE, (now, user_id, scope)
    result = await db.execute(sql, params)
    return int(getattr(result, "rowcount", 0) or 0)


async def mark_scope_seen(db: DbConnection, *, user_id: int, scope: str) -> int:
    """Legacy alias — use mark_scope_read."""
    return await mark_scope_read(db, user_id=user_id, scope=scope)


async def dismiss_notification(
    db: DbConnection,
    *,
    user_id: int,
    notification_id: int,
) -> bool:
    now = utcnow_str()
    pg = _is_postgres_connection(db)
    if pg:
        sql, params = _DISMISS_ONE_PG, (notification_id, user_id, now, now)
    else:
        sql, params = _DISMISS_ONE_SQLITE, (now, now, notification_id, user_id)
    result = await db.execute(sql, params)
    return int(getattr(result, "rowcount", 0) or 0) > 0


async def dismiss_all_notifications(
    db: DbConnection,
    *,
    user_id: int,
    scope: str,
) -> int:
    now = utcnow_str()
    pg = _is_postgres_connection(db)
    if scope == "all":
        sql = f"""
            UPDATE user_notifications
            SET dismissed_at = {_placeholder(pg, 2 if pg else 1)},
                read_at = COALESCE(read_at, {_placeholder(pg, 3 if pg else 2)})
            WHERE user_id = {_placeholder(pg, 1 if pg else 3)}
              AND dismissed_at IS NULL
            """
        params = (user_id, now, now) if pg else (now, now, user_id)
    elif pg:
        sql, params = _DISMISS_ALL_PG, (user_id, scope, now, now)
    else:
        sql, params = _DISMISS_ALL_SQLITE, (now, now, user_id, scope)
    result = await db.execute(sql, params)
    return int(getattr(result, "rowcount", 0) or 0)


async def undo_dismiss_notification(
    db: DbConnection,
    *,
    user_id: int,
    notification_id: int,
) -> bool:
    pg = _is_postgres_connection(db)
    result = await db.execute(
        f"""
        UPDATE user_notifications
        SET dismissed_at = NULL
        WHERE id = {_placeholder(pg, 1)} AND user_id = {_placeholder(pg, 2)}
        """,
        (notification_id, user_id),
    )
    return int(getattr(result, "rowcount", 0) or 0) > 0
