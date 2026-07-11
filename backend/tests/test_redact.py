"""Tests for shared secret/url redaction helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redact import mask_audit_log_target, mask_config_value, mask_secret_value, redact_audit_target


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
