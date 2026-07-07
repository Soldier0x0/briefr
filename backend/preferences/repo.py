"""DB access for per-user stack terms and optional asset profile."""

from __future__ import annotations

import json
from typing import Any

from db.dialect import utcnow_str

from preferences.validate import encode_profile, sanitize_profile


def _decode_profile(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return sanitize_profile(data)


async def get_user_stack(db: Any, user_id: int) -> dict:
    rows = await db.execute_fetchall(
        """
        SELECT stack_terms, profile_json, updated_at
        FROM user_preferences
        WHERE user_id = ?
        """,
        (user_id,),
    )
    if not rows:
        return {"stack_terms": "", "profile": None, "updated_at": None}
    row = rows[0]
    return {
        "stack_terms": row["stack_terms"] or "",
        "profile": _decode_profile(row["profile_json"]),
        "updated_at": row["updated_at"],
    }


async def upsert_user_stack(
    db: Any,
    user_id: int,
    stack_terms: str,
    profile: dict | None,
) -> dict:
    profile_json = encode_profile(profile)
    updated_at = utcnow_str()
    await db.execute(
        """
        INSERT INTO user_preferences (user_id, stack_terms, profile_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            stack_terms = excluded.stack_terms,
            profile_json = excluded.profile_json,
            updated_at = excluded.updated_at
        """,
        (user_id, stack_terms, profile_json, updated_at),
    )
    return {
        "stack_terms": stack_terms,
        "profile": profile,
        "updated_at": updated_at,
    }
