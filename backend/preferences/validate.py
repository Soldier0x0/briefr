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
    return {
        "version": data.get("version") or 1,
        "operatingSystems": data.get("operatingSystems")
        if isinstance(data.get("operatingSystems"), list)
        else [],
        "applications": data.get("applications")
        if isinstance(data.get("applications"), list)
        else [],
        "environment": {
            "internetFacing": env.get("internetFacing") or "Some",
            "industry": env.get("industry") or "Technology",
            "criticality": env.get("criticality") or "Medium",
        },
        "aiSystems": data.get("aiSystems") if isinstance(data.get("aiSystems"), list) else [],
    }


def encode_profile(profile: dict | None) -> str | None:
    if profile is None:
        return None
    import json

    encoded = json.dumps(profile, separators=(",", ":"), sort_keys=True)
    if len(encoded) > MAX_PROFILE_JSON_LEN:
        raise ValueError(f"profile JSON must be at most {MAX_PROFILE_JSON_LEN} characters")
    return encoded
