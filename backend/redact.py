"""Shared secret/url masking for admin config, audit logs, and API responses."""

from __future__ import annotations

from config_schema import get_field


def mask_secret_value(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "not configured"
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


def mask_url_value(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "not configured"
    if len(text) <= 30:
        return text[:8] + "…[masked]"
    return text[:30] + "…[masked]"


def mask_config_value(key: str, value: str) -> str:
    """Mask a config value for API responses based on schema field type."""
    field = get_field(key)
    if field is None:
        return value
    if field.type == "secret":
        return mask_secret_value(value)
    if field.type == "url":
        return mask_url_value(value)
    if key == "DATABASE_URL":
        return mask_url_value(value)
    return value


def redact_audit_target(action: str, key: str, value: str) -> str:
    """Redact sensitive values before writing audit_log.target."""
    if action.startswith("config.set."):
        field = get_field(key)
        if field and field.type in {"secret", "url"}:
            return mask_secret_value(value) if field.type == "secret" else mask_url_value(value)
        if key == "DATABASE_URL":
            return mask_url_value(value)
    if len(value) > 200:
        return value[:200] + "…"
    return value
