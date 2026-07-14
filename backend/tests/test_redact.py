"""Tests for shared secret/url redaction helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redact import (
    mask_audit_log_target,
    mask_config_value,
    mask_secret_value,
    mask_webhook_delivery_error,
    redact_audit_target,
)


def test_mask_secret_value_first4_last4():
    assert mask_secret_value("supersecretkey1234") == "supe…1234"


def test_mask_secret_value_short():
    assert mask_secret_value("short") == "***"


def test_mask_config_value_secret_key():
    masked = mask_config_value("NVD_API_KEY", "supersecretkey1234")
    assert "supersecretkey" not in masked
    assert masked == "supe…1234"


def test_redact_audit_target_masks_secret_config_set():
    target = redact_audit_target("config.set.NVD_API_KEY", "NVD_API_KEY", "supersecretkey1234")
    assert "supersecretkey" not in target
    assert target == "supe…1234"


def test_redact_audit_target_passes_through_non_secret():
    target = redact_audit_target("config.set.NVD_SYNC_INTERVAL_HOURS", "NVD_SYNC_INTERVAL_HOURS", "6")
    assert target == "6"


def test_mask_audit_log_target_masks_legacy_plaintext_secret():
    secret = "gsk_te5zV2BGuRmNpqrstuvwxyz1234"
    masked = mask_audit_log_target("config.set.GROQ_API_KEY", secret)
    assert secret not in masked
    assert masked == "gsk_…1234"


def test_mask_audit_log_target_preserves_non_secret():
    assert mask_audit_log_target("config.set.NVD_SYNC_INTERVAL_HOURS", "6") == "6"


def test_mask_audit_log_target_preserves_already_masked():
    masked = "gsk_…1234"
    assert mask_audit_log_target("config.set.GROQ_API_KEY", masked) == masked


def test_redact_audit_metadata_masks_secret_values():
    from redact import mask_audit_log_metadata, redact_audit_metadata

    secret = "gsk_legacyPlaintextKey9999"
    raw = {"value": secret}
    stored = redact_audit_metadata("config.set.GROQ_API_KEY", raw)
    assert secret not in stored["value"]
    assert "…" in stored["value"]

    masked = mask_audit_log_metadata("config.set.GROQ_API_KEY", raw)
    assert secret not in masked["value"]


def test_redact_audit_metadata_preserves_config_apply_key_names():
    from redact import mask_audit_log_metadata, redact_audit_metadata

    long_key = "CORRELATION_OBSERVATION_RETENTION_DAYS"
    raw = {"changed_keys": [long_key], "restart_needed": False}
    stored = redact_audit_metadata("config.apply", raw)
    assert stored["changed_keys"] == [long_key]

    masked = mask_audit_log_metadata("config.apply", raw)
    assert masked["changed_keys"] == [long_key]


def test_mask_webhook_delivery_error_redacts_urls():
    err = "HTTP 401 https://discord.com/api/webhooks/abc/TOKEN123"
    masked = mask_webhook_delivery_error(err)
    assert "discord.com" not in masked
    assert "TOKEN123" not in masked
    assert "[redacted-url]" in masked


def test_mask_webhook_delivery_error_redacts_sensitive_keywords():
    assert mask_webhook_delivery_error("invalid token in payload") == "[redacted]"


def test_mask_webhook_delivery_error_passes_short_safe_errors():
    assert mask_webhook_delivery_error("timeout") == "timeout"
    assert mask_webhook_delivery_error(None) is None
