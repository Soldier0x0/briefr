"""DB access for built-in app login: users + sessions.

Mirrors the free-function-taking-a-db-connection style used throughout
database.py. Callers own the connection lifecycle (acquire, commit, close).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auth.passwords import hash_password
from auth.tokens import hash_refresh_token
from auth.usernames import normalize_username


async def count_users(db: Any) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS n FROM users")
    return rows[0]["n"]


async def get_user_by_username(db: Any, username: str) -> dict | None:
    rows = await db.execute_fetchall(
        """
        SELECT id, username, password_hash, role, is_active, created_at, last_login_at
        FROM users
        WHERE username = ?
        """,
        (normalize_username(username),),
    )
    return dict(rows[0]) if rows else None


async def get_user_by_id(db: Any, user_id: int) -> dict | None:
    rows = await db.execute_fetchall(
        """
        SELECT id, username, password_hash, role, is_active, created_at, last_login_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return dict(rows[0]) if rows else None


async def create_user(
    db: Any, username: str, password: str, role: str = "admin"
) -> dict:
    """Insert a new user, or update the password hash if the username already
    exists (idempotent — also serves as the interim password-reset path)."""
    normalized = normalize_username(username)
    password_hash = hash_password(password)

    existing = await get_user_by_username(db, normalized)
    if existing is not None:
        await db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, existing["id"]),
        )
        existing["password_hash"] = password_hash
        return existing

    rows = await db.execute_fetchall(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
        RETURNING id, username, password_hash, role, is_active, created_at, last_login_at
        """,
        (normalized, password_hash, role),
    )
    return dict(rows[0])


async def update_last_login(db: Any, user_id: int) -> None:
    await db.execute(
        "UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
        (user_id,),
    )


async def create_session(
    db: Any,
    user_id: int,
    refresh_token: str,
    expires_at: str,
    user_agent: str = "",
    ip: str = "",
    remember_me: bool = False,
) -> dict:
    rows = await db.execute_fetchall(
        """
        INSERT INTO sessions (user_id, refresh_token_hash, expires_at, user_agent, ip, remember_me)
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id, user_id, refresh_token_hash, created_at, last_used_at,
                  expires_at, revoked_at, user_agent, ip, remember_me
        """,
        (user_id, hash_refresh_token(refresh_token), expires_at, user_agent, ip, int(remember_me)),
    )
    return dict(rows[0])


async def get_session_by_token(db: Any, refresh_token: str) -> dict | None:
    rows = await db.execute_fetchall(
        """
        SELECT id, user_id, refresh_token_hash, created_at, last_used_at,
               expires_at, revoked_at, user_agent, ip, remember_me
        FROM sessions
        WHERE refresh_token_hash = ?
        """,
        (hash_refresh_token(refresh_token),),
    )
    return dict(rows[0]) if rows else None


async def rotate_session(
    db: Any,
    old_session: dict,
    new_refresh_token: str,
    expires_at: str,
) -> dict:
    """Revoke ``old_session`` (its row and hash are left intact, so a later
    replay of the same now-stale token is detectable as reuse) and create a
    fresh session row for the rotated token, carrying forward its
    remember_me flag so cookie persistence survives rotation."""
    await db.execute(
        """
        UPDATE sessions
        SET revoked_at = datetime('now'), last_used_at = datetime('now')
        WHERE id = ?
        """,
        (old_session["id"],),
    )
    return await create_session(
        db,
        old_session["user_id"],
        new_refresh_token,
        expires_at,
        user_agent=old_session.get("user_agent", ""),
        ip=old_session.get("ip", ""),
        remember_me=bool(old_session.get("remember_me")),
    )


async def revoke_session(db: Any, session_id: int) -> None:
    await db.execute(
        "UPDATE sessions SET revoked_at = datetime('now') WHERE id = ? AND revoked_at IS NULL",
        (session_id,),
    )


async def revoke_all_sessions_for_user(db: Any, user_id: int) -> None:
    await db.execute(
        "UPDATE sessions SET revoked_at = datetime('now') WHERE user_id = ? AND revoked_at IS NULL",
        (user_id,),
    )


async def list_active_sessions(db: Any, user_id: int) -> list[dict]:
    rows = await db.execute_fetchall(
        """SELECT id, refresh_token_hash, created_at, last_used_at, expires_at, user_agent, ip, remember_me
           FROM sessions
           WHERE user_id = ? AND revoked_at IS NULL
           ORDER BY last_used_at DESC""",
        (user_id,),
    )
    return [dict(r) for r in rows]


async def purge_expired_sessions(db: Any) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    result = await db.execute(
        "DELETE FROM sessions WHERE expires_at < ?",
        (now,),
    )
    return result.rowcount
