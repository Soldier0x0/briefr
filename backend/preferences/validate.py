"""Validation for per-user stack terms and asset profile JSON."""

from __future__ import annotations

MAX_STACK_TERMS_LEN = 4096
MAX_PROFILE_JSON_LEN = 65536


def normalize_stack_terms(raw: str) -> str:
    parts = [part.strip() for part in (raw or "").split(",") if part.strip()]
    return ",".join(parts)


def validate_stack_terms(raw: str) -> str:
    if raw is None:
        raise ValueError("stack_terms must be a string")
    if len(raw) > MAX_STACK_TERMS_LEN:
        raise ValueError(f"stack_terms must be at most {MAX_STACK_TERMS_LEN} characters")
    return normalize_stack_terms(raw)


def sanitize_profile(data: dict | None) -> dict | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("profile must be a JSON object")

    env = data.get("environment") if isinstance(data.get("environment"), dict) else {}

    os_list = []
    raw_os = data.get("operatingSystems")
    if isinstance(raw_os, list):
        for item in raw_os:
            if isinstance(item, dict):
                os_list.append({
                    "product": str(item.get("product") or ""),
                    "version": str(item.get("version") or ""),
                    "vendor": str(item.get("vendor") or ""),
                })

    apps_list = []
    raw_apps = data.get("applications")
    if isinstance(raw_apps, list):
        for item in raw_apps:
            if isinstance(item, dict):
                apps_list.append({
                    "product": str(item.get("product") or ""),
                    "cpeProduct": str(item.get("cpeProduct") or ""),
                    "version": str(item.get("version") or ""),
                    "vendor": str(item.get("vendor") or ""),
                })

    ai_list = []
    raw_ai = data.get("aiSystems")
    if isinstance(raw_ai, list):
        for item in raw_ai:
            if item is not None:
                ai_list.append(str(item))

    return {
        "version": data.get("version") or 1,
        "operatingSystems": os_list,
        "applications": apps_list,
        "environment": {
            "internetFacing": str(env.get("internetFacing") or "Some"),
            "industry": str(env.get("industry") or "Technology"),
            "criticality": str(env.get("criticality") or "Medium"),
        },
        "aiSystems": ai_list,
    }


def encode_profile(profile: dict | None) -> str | None:
    if profile is None:
        return None
    import json

    encoded = json.dumps(profile, separators=(",", ":"), sort_keys=True)
    if len(encoded) > MAX_PROFILE_JSON_LEN:
        raise ValueError(f"profile JSON must be at most {MAX_PROFILE_JSON_LEN} characters")
    return encoded
