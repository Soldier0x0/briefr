"""DB access for per-user stack terms and optional asset profile."""

from __future__ import annotations

import json
from typing import Any

from db.dialect import utcnow_str

from preferences.display_validate import (
    DEFAULT_DISPLAY_PREFS,
    encode_display_prefs,
    merge_display_prefs,
    sanitize_display_prefs,
    validate_timezone,
)
from preferences.validate import encode_profile, sanitize_profile


def _decode_display_prefs(raw: str | None) -> dict:
    if not raw:
        return dict(DEFAULT_DISPLAY_PREFS)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULT_DISPLAY_PREFS)
    if not isinstance(data, dict):
        return dict(DEFAULT_DISPLAY_PREFS)
    try:
        return sanitize_display_prefs(data)
    except ValueError:
        return dict(DEFAULT_DISPLAY_PREFS)


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


async def get_effective_stack_terms(db: Any) -> str:
    """Operator stack for KEV alerts / wallboard: env override, else saved user stack."""
    from db.sync_state import get_stack_terms

    env_stack = (get_stack_terms() or "").strip()
    if env_stack:
        return env_stack
    rows = await db.execute_fetchall(
        """
        SELECT stack_terms
        FROM user_preferences
        WHERE TRIM(stack_terms) != ''
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if not rows:
        return ""
    return (rows[0]["stack_terms"] or "").strip()


async def get_user_preferences(db: Any, user_id: int) -> dict:
    rows = await db.execute_fetchall(
        """
        SELECT display_prefs_json, timezone, updated_at
        FROM user_preferences
        WHERE user_id = ?
        """,
        (user_id,),
    )
    if not rows:
        prefs = dict(DEFAULT_DISPLAY_PREFS)
        return {
            **prefs,
            "timezone": "UTC",
            "updated_at": None,
        }
    row = rows[0]
    prefs = _decode_display_prefs(row["display_prefs_json"])
    try:
        tz = validate_timezone(row["timezone"] or "UTC")
    except ValueError:
        tz = "UTC"
    return {
        **prefs,
        "timezone": tz,
        "updated_at": row["updated_at"],
    }


async def patch_user_preferences(db: Any, user_id: int, patch: dict) -> dict:
    current = await get_user_preferences(db, user_id)
    updated_at = current["updated_at"]

    display_patch = {
        key: patch[key]
        for key in (
            "font_scale",
            "density",
            "show_technical_ids",
            "poll_interval_seconds",
            "utc_time",
            "reduce_motion",
        )
        if key in patch
    }
    prefs = merge_display_prefs(
        {k: current[k] for k in DEFAULT_DISPLAY_PREFS},
        display_patch,
    )
    timezone = validate_timezone(patch["timezone"]) if "timezone" in patch else current["timezone"]
    display_json = encode_display_prefs(prefs)
    updated_at = utcnow_str()

    await db.execute(
        """
        INSERT INTO user_preferences (user_id, display_prefs_json, timezone, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_prefs_json = excluded.display_prefs_json,
            timezone = excluded.timezone,
            updated_at = excluded.updated_at
        """,
        (user_id, display_json, timezone, updated_at),
    )
    return {
        **prefs,
        "timezone": timezone,
        "updated_at": updated_at,
    }
