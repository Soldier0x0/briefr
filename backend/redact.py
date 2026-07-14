"""Shared secret/url masking for admin config, audit logs, and API responses."""

from __future__ import annotations

import re

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


_SECRET_PREFIXES = (
    "gsk_",
    "sk-or-v1-",
    "sk-",
    "sk_",
    "csk-",
    "vulncheck_",
    "aq.",
)


def _already_masked_secret(text: str) -> bool:
    return (
        text in {"***", "not configured"}
        or "…" in text
        or "[masked]" in text.lower()
    )


def _looks_like_secret_value(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) < 9 or _already_masked_secret(stripped):
        return False
    lower = stripped.lower()
    if any(lower.startswith(prefix) for prefix in _SECRET_PREFIXES):
        return True
    if len(stripped) > 24 and " " not in stripped and "/" not in stripped:
        return True
    return False


def mask_audit_log_target(action: str, target: str | None) -> str:
    """Mask sensitive audit_log.target values on read (covers legacy plaintext rows)."""
    text = (target or "").strip()
    if not text:
        return text
    if _already_masked_secret(text):
        return text

    if action.startswith("config.set."):
        key = action.removeprefix("config.set.")
        field = get_field(key)
        if field and field.type == "secret":
            return mask_secret_value(text)
        if field and field.type == "url":
            return mask_url_value(text)
        if key == "DATABASE_URL":
            return mask_url_value(text)

    if action.startswith("config.") and _looks_like_secret_value(text):
        return mask_secret_value(text)

    if len(text) > 200:
        return text[:200] + "…"
    return text


_WEBHOOK_ERROR_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def mask_webhook_delivery_error(error: str | None) -> str | None:
    """Mask webhook delivery errors for admin APIs (URLs/tokens must not leak)."""
    if error is None:
        return None
    text = str(error).strip()
    if not text:
        return text
    if _WEBHOOK_ERROR_URL_RE.search(text):
        text = _WEBHOOK_ERROR_URL_RE.sub("[redacted-url]", text)
    lower = text.lower()
    if len(text) > 80 or "token" in lower or "password" in lower or "secret" in lower:
        return "[redacted]"
    return text


def redact_audit_metadata(action: str, metadata: dict | None) -> dict | None:
    """Redact sensitive values before persisting audit_log.metadata_json."""
    if not metadata:
        return None
    return _mask_metadata_tree(action, metadata)


def mask_audit_log_metadata(action: str, metadata: dict | None) -> dict | None:
    """Mask sensitive metadata values on read (covers legacy plaintext in JSON)."""
    if not metadata:
        return None
    return _mask_metadata_tree(action, metadata)


def _mask_metadata_tree(action: str, value):
    if isinstance(value, dict):
        return {k: _mask_metadata_tree(action, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_metadata_tree(action, v) for v in value]
    if isinstance(value, str):
        if action.startswith("config.set.") and _looks_like_secret_value(value):
            return mask_secret_value(value)
        if len(value) > 500:
            return value[:500] + "…"
    return value
