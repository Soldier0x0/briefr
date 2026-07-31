"""DB access for per-user stack terms and optional asset profile."""

from __future__ import annotations

import json
from typing import Any

from db.timeutil import utcnow_str

from preferences.display_validate import (
    DEFAULT_DISPLAY_PREFS,
    INSTANCE_TYPOGRAPHY_SETTING_KEY,
    INSTANCE_UI_VARIANT_SETTING_KEY,
    encode_display_prefs,
    merge_display_prefs,
    sanitize_display_prefs,
    sanitize_typography_px,
    sanitize_ui_variant,
    validate_timezone,
)
from preferences.validate import encode_profile, sanitize_profile


def _decode_display_prefs(
    raw: str | None,
    *,
    instance_typography: dict | None = None,
    instance_ui_variant: str | None = None,
) -> dict:
    fallback_ui_variant = sanitize_ui_variant(instance_ui_variant)
    if not raw:
        prefs = dict(DEFAULT_DISPLAY_PREFS)
        prefs["typography_px"] = sanitize_typography_px(instance_typography)
        prefs["ui_variant"] = fallback_ui_variant
        return prefs
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        prefs = dict(DEFAULT_DISPLAY_PREFS)
        prefs["typography_px"] = sanitize_typography_px(instance_typography)
        prefs["ui_variant"] = fallback_ui_variant
        return prefs
    if not isinstance(data, dict):
        prefs = dict(DEFAULT_DISPLAY_PREFS)
        prefs["typography_px"] = sanitize_typography_px(instance_typography)
        prefs["ui_variant"] = fallback_ui_variant
        return prefs
    try:
        prefs = sanitize_display_prefs(data)
    except ValueError:
        prefs = dict(DEFAULT_DISPLAY_PREFS)
    if "typography_px" in data:
        try:
            prefs["typography_px"] = sanitize_typography_px(data.get("typography_px"))
        except ValueError:
            prefs["typography_px"] = sanitize_typography_px(instance_typography)
    else:
        prefs["typography_px"] = sanitize_typography_px(instance_typography)
    if "ui_variant" not in data:
        prefs["ui_variant"] = fallback_ui_variant
    return prefs


async def get_instance_typography_default(db: Any) -> dict | None:
    from db.app_settings import get_app_setting

    raw = await get_app_setting(db, INSTANCE_TYPOGRAPHY_SETTING_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        return sanitize_typography_px(data)
    except ValueError:
        return None


async def set_instance_typography_default(db: Any, typography_px: dict) -> dict:
    from db.app_settings import set_app_setting

    sanitized = sanitize_typography_px(typography_px)
    await set_app_setting(
        db,
        INSTANCE_TYPOGRAPHY_SETTING_KEY,
        json.dumps(sanitized, separators=(",", ":"), sort_keys=True),
    )
    return sanitized


async def get_instance_ui_variant_default(db: Any) -> str | None:
    from db.app_settings import get_app_setting

    raw = await get_app_setting(db, INSTANCE_UI_VARIANT_SETTING_KEY)
    if not raw:
        return None
    try:
        return sanitize_ui_variant(raw)
    except ValueError:
        return None


async def set_instance_ui_variant_default(db: Any, ui_variant: str) -> str:
    from db.app_settings import set_app_setting

    sanitized = sanitize_ui_variant(ui_variant)
    await set_app_setting(db, INSTANCE_UI_VARIANT_SETTING_KEY, sanitized)
    return sanitized


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
    profile: dict | None = None,
    *,
    update_profile: bool = False,
) -> dict:
    updated_at = utcnow_str()
    if update_profile:
        profile_json = encode_profile(profile)
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

    await db.execute(
        """
        INSERT INTO user_preferences (user_id, stack_terms, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            stack_terms = excluded.stack_terms,
            updated_at = excluded.updated_at
        """,
        (user_id, stack_terms, updated_at),
    )
    saved = await get_user_stack(db, user_id)
    return {
        "stack_terms": stack_terms,
        "profile": saved["profile"],
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
    instance_typography = await get_instance_typography_default(db)
    instance_ui_variant = await get_instance_ui_variant_default(db)
    rows = await db.execute_fetchall(
        """
        SELECT display_prefs_json, timezone, remember_profile_on_server, updated_at
        FROM user_preferences
        WHERE user_id = ?
        """,
        (user_id,),
    )
    if not rows:
        prefs = dict(DEFAULT_DISPLAY_PREFS)
        prefs["typography_px"] = sanitize_typography_px(instance_typography)
        prefs["ui_variant"] = sanitize_ui_variant(instance_ui_variant)
        return {
            **prefs,
            "timezone": "UTC",
            "remember_profile_on_server": False,
            "updated_at": None,
            "instance_typography_default": instance_typography,
            "instance_ui_variant_default": instance_ui_variant,
        }
    row = rows[0]
    prefs = _decode_display_prefs(
        row["display_prefs_json"],
        instance_typography=instance_typography,
        instance_ui_variant=instance_ui_variant,
    )
    try:
        tz = validate_timezone(row["timezone"] or "UTC")
    except ValueError:
        tz = "UTC"
    return {
        **prefs,
        "timezone": tz,
        "remember_profile_on_server": bool(row["remember_profile_on_server"]),
        "updated_at": row["updated_at"],
        "instance_typography_default": instance_typography,
        "instance_ui_variant_default": instance_ui_variant,
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
            "notification_sound",
            "ui_variant",
            "typography_px",
        )
        if key in patch
    }
    existing_for_merge = {k: current[k] for k in DEFAULT_DISPLAY_PREFS if k in current}
    if "typography_px" in current:
        existing_for_merge["typography_px"] = current["typography_px"]
    prefs = merge_display_prefs(existing_for_merge, display_patch)
    timezone = validate_timezone(patch["timezone"]) if "timezone" in patch else current["timezone"]
    remember = (
        bool(patch["remember_profile_on_server"])
        if "remember_profile_on_server" in patch
        else current["remember_profile_on_server"]
    )
    display_json = encode_display_prefs(prefs)
    updated_at = utcnow_str()

    await db.execute(
        """
        INSERT INTO user_preferences (user_id, display_prefs_json, timezone, remember_profile_on_server, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_prefs_json = excluded.display_prefs_json,
            timezone = excluded.timezone,
            remember_profile_on_server = excluded.remember_profile_on_server,
            updated_at = excluded.updated_at
        """,
        (user_id, display_json, timezone, int(remember), updated_at),
    )
    return {
        **prefs,
        "timezone": timezone,
        "remember_profile_on_server": remember,
        "updated_at": updated_at,
        "instance_typography_default": current.get("instance_typography_default"),
        "instance_ui_variant_default": current.get("instance_ui_variant_default"),
    }
