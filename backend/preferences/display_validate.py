"""Validation for per-user display preferences and timezone."""

from __future__ import annotations

from zoneinfo import ZoneInfo

FONT_SCALES = frozenset({"xsmall", "small", "medium", "large", "xlarge"})
DENSITY_MODES = frozenset({"compact", "comfortable", "spacious"})
POLL_INTERVALS = frozenset({15, 30, 60, 120})
MAX_DISPLAY_PREFS_JSON_LEN = 4096
MAX_TIMEZONE_LEN = 64

DEFAULT_DISPLAY_PREFS = {
    "font_scale": "medium",
    "density": "comfortable",
    "show_technical_ids": False,
    "poll_interval_seconds": 30,
    "utc_time": False,
    "reduce_motion": False,
    "notification_sound": True,
}


def validate_timezone(raw: str | None) -> str:
    token = (raw or "UTC").strip()
    if not token:
        token = "UTC"
    if len(token) > MAX_TIMEZONE_LEN:
        raise ValueError(f"timezone must be at most {MAX_TIMEZONE_LEN} characters")
    try:
        ZoneInfo(token)
    except Exception as exc:
        raise ValueError("timezone is not a valid IANA zone") from exc
    return token


def _coerce_bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field} must be a boolean")


def sanitize_display_prefs(data: dict | None) -> dict:
    base = dict(DEFAULT_DISPLAY_PREFS)
    if data is None:
        return base
    if not isinstance(data, dict):
        raise ValueError("display preferences must be a JSON object")

    if "font_scale" in data and data["font_scale"] is not None:
        font_scale = str(data["font_scale"]).strip()
        if font_scale not in FONT_SCALES:
            raise ValueError("font_scale is invalid")
        base["font_scale"] = font_scale

    if "density" in data and data["density"] is not None:
        density = str(data["density"]).strip()
        if density not in DENSITY_MODES:
            raise ValueError("density is invalid")
        base["density"] = density

    if "show_technical_ids" in data and data["show_technical_ids"] is not None:
        base["show_technical_ids"] = _coerce_bool(data["show_technical_ids"], "show_technical_ids")

    if "poll_interval_seconds" in data and data["poll_interval_seconds"] is not None:
        try:
            poll = int(data["poll_interval_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValueError("poll_interval_seconds must be an integer") from exc
        if poll not in POLL_INTERVALS:
            raise ValueError("poll_interval_seconds is invalid")
        base["poll_interval_seconds"] = poll

    if "utc_time" in data and data["utc_time"] is not None:
        base["utc_time"] = _coerce_bool(data["utc_time"], "utc_time")

    if "reduce_motion" in data and data["reduce_motion"] is not None:
        base["reduce_motion"] = _coerce_bool(data["reduce_motion"], "reduce_motion")

    if "notification_sound" in data and data["notification_sound"] is not None:
        base["notification_sound"] = _coerce_bool(data["notification_sound"], "notification_sound")

    return base


def merge_display_prefs(existing: dict, patch: dict) -> dict:
    merged = dict(existing)
    for key, value in patch.items():
        if value is not None:
            merged[key] = value
    return sanitize_display_prefs(merged)


def encode_display_prefs(prefs: dict) -> str:
    import json

    encoded = json.dumps(prefs, separators=(",", ":"), sort_keys=True)
    if len(encoded) > MAX_DISPLAY_PREFS_JSON_LEN:
        raise ValueError(
            f"display preferences JSON must be at most {MAX_DISPLAY_PREFS_JSON_LEN} characters"
        )
    return encoded
