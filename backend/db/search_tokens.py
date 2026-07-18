"""Search service API tokens (Embeddings E5) — bcrypt at rest, show-once plaintext.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from auth.passwords import hash_password, verify_password
from db.timeutil import utcnow_str
from db.types import DbConnection

TOKEN_PREFIX = "briefr_search_"
# Indexed lookup key length: prefix + first 12 chars of secret.
LOOKUP_LEN = len(TOKEN_PREFIX) + 12
DEFAULT_SCOPES = ("search:semantic", "cves:related", "cves:read")


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def generate_search_token_plaintext() -> str:
    """Return a new plaintext token (show once)."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def token_lookup_prefix(plaintext: str) -> str:
    text = (plaintext or "").strip()
    if len(text) < LOOKUP_LEN:
        return text
    return text[:LOOKUP_LEN]


def scopes_json(scopes: list[str] | tuple[str, ...] | None = None) -> str:
    return json.dumps(list(scopes or DEFAULT_SCOPES))


def parse_scopes(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(s) for s in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return list(DEFAULT_SCOPES)
        if isinstance(parsed, list):
            return [str(s) for s in parsed]
    return list(DEFAULT_SCOPES)


async def create_search_token(
    db: DbConnection,
    *,
    name: str,
    created_by: str = "",
    scopes: list[str] | None = None,
) -> dict:
    """Insert a token row; returns metadata + plaintext ``token`` (once)."""
    label = (name or "").strip() or "Search token"
    plaintext = generate_search_token_plaintext()
    prefix = token_lookup_prefix(plaintext)
    token_hash = hash_password(plaintext)
    scope_blob = scopes_json(scopes)
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            """
            INSERT INTO search_api_tokens (
                name, token_prefix, token_hash, scopes, created_by
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, token_prefix, scopes, created_at, created_by,
                      last_used_at, revoked_at
            """,
            (label, prefix, token_hash, scope_blob, created_by or ""),
        )
        row = dict(rows[0])
    else:
        await db.execute(
            """
            INSERT INTO search_api_tokens (
                name, token_prefix, token_hash, scopes, created_at, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (label, prefix, token_hash, scope_blob, utcnow_str(), created_by or ""),
        )
        rows = await db.execute_fetchall(
            "SELECT id, name, token_prefix, scopes, created_at, created_by, "
            "last_used_at, revoked_at FROM search_api_tokens WHERE token_prefix = ?",
            (prefix,),
        )
        row = dict(rows[0])
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "token_prefix": row["token_prefix"],
        "scopes": parse_scopes(row.get("scopes")),
        "created_at": str(row.get("created_at") or ""),
        "created_by": row.get("created_by") or "",
        "last_used_at": row.get("last_used_at"),
        "revoked_at": row.get("revoked_at"),
        "token": plaintext,
    }


async def list_search_tokens(db: DbConnection) -> list[dict]:
    rows = await db.execute_fetchall(
        """
        SELECT id, name, token_prefix, scopes, created_at, created_by,
               last_used_at, revoked_at
        FROM search_api_tokens
        ORDER BY created_at DESC
        """
    )
    out = []
    for row in rows:
        item = dict(row)
        item["scopes"] = parse_scopes(item.get("scopes"))
        item["id"] = int(item["id"])
        item["active"] = item.get("revoked_at") is None
        out.append(item)
    return out


async def revoke_search_token(db: DbConnection, token_id: int) -> bool:
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            """
            UPDATE search_api_tokens
            SET revoked_at = NOW()
            WHERE id = $1 AND revoked_at IS NULL
            RETURNING id
            """,
            (token_id,),
        )
        return bool(rows)
    # SQLite: only succeed when an active row exists (match Postgres RETURNING).
    active = await db.execute_fetchall(
        "SELECT id FROM search_api_tokens WHERE id = ? AND revoked_at IS NULL",
        (token_id,),
    )
    if not active:
        return False
    await db.execute(
        """
        UPDATE search_api_tokens
        SET revoked_at = ?
        WHERE id = ? AND revoked_at IS NULL
        """,
        (utcnow_str(), token_id),
    )
    return True


async def verify_search_token(db: DbConnection, plaintext: str) -> dict | None:
    """Return token metadata when valid and not revoked; else None."""
    text = (plaintext or "").strip()
    if not text.startswith(TOKEN_PREFIX) or len(text) < LOOKUP_LEN:
        return None
    prefix = token_lookup_prefix(text)
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            """
            SELECT id, name, token_prefix, token_hash, scopes, created_at,
                   created_by, last_used_at, revoked_at
            FROM search_api_tokens
            WHERE token_prefix = $1 AND revoked_at IS NULL
            """,
            (prefix,),
        )
    else:
        rows = await db.execute_fetchall(
            """
            SELECT id, name, token_prefix, token_hash, scopes, created_at,
                   created_by, last_used_at, revoked_at
            FROM search_api_tokens
            WHERE token_prefix = ? AND revoked_at IS NULL
            """,
            (prefix,),
        )
    if not rows:
        return None
    row = dict(rows[0])
    if not verify_password(text, row["token_hash"]):
        return None
    # Touch last_used_at (best-effort).
    tid = int(row["id"])
    try:
        if pg:
            await db.execute(
                "UPDATE search_api_tokens SET last_used_at = NOW() WHERE id = $1",
                (tid,),
            )
        else:
            await db.execute(
                "UPDATE search_api_tokens SET last_used_at = ? WHERE id = ?",
                (utcnow_str(), tid),
            )
        await db.commit()
    except Exception:
        pass
    return {
        "id": tid,
        "name": row["name"],
        "token_prefix": row["token_prefix"],
        "scopes": parse_scopes(row.get("scopes")),
        "auth_type": "search_token",
    }
