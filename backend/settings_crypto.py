"""Encrypt secret-typed operator settings at rest in `app_settings`.

See docs/decisions/ADR-006-encrypted-app-settings-secrets.md.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

ENC_PREFIX = "enc:v1:"
SETTINGS_KEY_ENV = "BRIEFR_SETTINGS_KEY"


def settings_key_configured() -> bool:
    raw = os.environ.get(SETTINGS_KEY_ENV, "").strip()
    return bool(raw)


def _fernet():
    """Return a Fernet instance or None when BRIEFR_SETTINGS_KEY is unset."""
    raw = os.environ.get(SETTINGS_KEY_ENV, "").strip()
    if not raw:
        return None
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted_value(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def encrypt_secret(plaintext: str) -> str | None:
    """Encrypt plaintext for DB storage. None if key missing (caller should skip persist)."""
    f = _fernet()
    if f is None:
        return None
    token = f.encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    """Decrypt an enc:v1: value, or return plaintext unchanged (legacy rows)."""
    if not is_encrypted_value(stored):
        return stored
    f = _fernet()
    if f is None:
        raise ValueError(
            f"{SETTINGS_KEY_ENV} is required to decrypt encrypted app_settings secrets"
        )
    from cryptography.fernet import InvalidToken

    token = stored[len(ENC_PREFIX) :].encode("ascii")
    try:
        return f.decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt app_settings secret (wrong key?)") from exc
