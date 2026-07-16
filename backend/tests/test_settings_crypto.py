"""ADR-006: encrypt secret-typed app_settings values."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from settings_crypto import (
    ENC_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_value,
    settings_key_configured,
)


def test_encrypt_requires_settings_key(monkeypatch):
    monkeypatch.delenv("BRIEFR_SETTINGS_KEY", raising=False)
    assert settings_key_configured() is False
    assert encrypt_secret("nvd-key") is None


def test_encrypt_decrypt_round_trip(monkeypatch):
    monkeypatch.setenv("BRIEFR_SETTINGS_KEY", "test-settings-master-key-not-for-prod")
    assert settings_key_configured() is True
    stored = encrypt_secret("super-secret-nvd")
    assert stored is not None
    assert is_encrypted_value(stored)
    assert stored.startswith(ENC_PREFIX)
    assert "super-secret-nvd" not in stored
    assert decrypt_secret(stored) == "super-secret-nvd"


def test_decrypt_legacy_plaintext_passthrough(monkeypatch):
    monkeypatch.setenv("BRIEFR_SETTINGS_KEY", "k")
    assert decrypt_secret("already-plain") == "already-plain"


def test_decrypt_encrypted_without_key_raises(monkeypatch):
    monkeypatch.setenv("BRIEFR_SETTINGS_KEY", "k")
    stored = encrypt_secret("x")
    monkeypatch.delenv("BRIEFR_SETTINGS_KEY", raising=False)
    with pytest.raises(ValueError, match="BRIEFR_SETTINGS_KEY"):
        decrypt_secret(stored)
