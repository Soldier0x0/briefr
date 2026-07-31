"""Validation for per-user display preferences and timezone."""

from __future__ import annotations

from zoneinfo import ZoneInfo

FONT_SCALES = frozenset({"xsmall", "small", "medium", "large", "xlarge"})
DENSITY_MODES = frozenset({"compact", "comfortable", "spacious"})
POLL_INTERVALS = frozenset({15, 30, 60, 120})
MAX_DISPLAY_PREFS_JSON_LEN = 4096
MAX_TIMEZONE_LEN = 64

UI_VARIANTS = frozenset({"default", "pitch"})

DEFAULT_DISPLAY_PREFS = {
    "font_scale": "medium",
    "density": "comfortable",
    "show_technical_ids": False,
    "poll_interval_seconds": 30,
    "utc_time": False,
    "reduce_motion": False,
    "notification_sound": True,
    "ui_variant": "pitch",
}

DEFAULT_TYPOGRAPHY_PX = {
    "title": 20,
    "heading": 15,
    "subheading": 14,
    "id": 18,
    "body": 14,
    "meta": 13,
    "micro": 12,
}
TYPOGRAPHY_ROLES = frozenset(DEFAULT_TYPOGRAPHY_PX)
MIN_TYPOGRAPHY_PX = 9
MAX_TYPOGRAPHY_PX = 20
INSTANCE_TYPOGRAPHY_SETTING_KEY = "display_typography_default"
INSTANCE_UI_VARIANT_SETTING_KEY = "display_ui_variant_default"


def sanitize_ui_variant(value: object | None) -> str:
    if value is None:
        return DEFAULT_DISPLAY_PREFS["ui_variant"]
    token = str(value).strip()
    if token not in UI_VARIANTS:
        raise ValueError("ui_variant is invalid")
    return token


def sanitize_typography_px(data: dict | None) -> dict:
    base = dict(DEFAULT_TYPOGRAPHY_PX)
    if data is None:
        return base
    if not isinstance(data, dict):
        raise ValueError("typography_px must be a JSON object")
    for role in TYPOGRAPHY_ROLES:
        if role not in data or data[role] is None:
            continue
        try:
            px = int(data[role])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"typography_px.{role} must be an integer") from exc
        if px < MIN_TYPOGRAPHY_PX or px > MAX_TYPOGRAPHY_PX:
            raise ValueError(
                f"typography_px.{role} must be between {MIN_TYPOGRAPHY_PX} and {MAX_TYPOGRAPHY_PX}"
            )
        base[role] = px
    return base

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

    if "ui_variant" in data and data["ui_variant"] is not None:
        ui_variant = str(data["ui_variant"]).strip()
        if ui_variant not in UI_VARIANTS:
            raise ValueError("ui_variant is invalid")
        base["ui_variant"] = ui_variant

    return base


def merge_display_prefs(existing: dict, patch: dict) -> dict:
    merged = {k: existing[k] for k in DEFAULT_DISPLAY_PREFS if k in existing}
    if "typography_px" in existing:
        merged["typography_px"] = existing["typography_px"]
    for key, value in patch.items():
        if value is None:
            continue
        if key == "typography_px":
            base = dict(merged.get("typography_px") or DEFAULT_TYPOGRAPHY_PX)
            if isinstance(value, dict):
                base.update(value)
            merged["typography_px"] = sanitize_typography_px(base)
        elif key in DEFAULT_DISPLAY_PREFS:
            merged[key] = value
    result = sanitize_display_prefs(merged)
    if "typography_px" in merged:
        result["typography_px"] = merged["typography_px"]
    return result


def encode_display_prefs(prefs: dict) -> str:
    import json

    payload = {k: prefs[k] for k in DEFAULT_DISPLAY_PREFS if k in prefs}
    if "typography_px" in prefs:
        payload["typography_px"] = prefs["typography_px"]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if len(encoded) > MAX_DISPLAY_PREFS_JSON_LEN:
        raise ValueError(
            f"display preferences JSON must be at most {MAX_DISPLAY_PREFS_JSON_LEN} characters"
        )
    return encoded
