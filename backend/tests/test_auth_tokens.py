"""Tests for auth/tokens.py."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
import pytest

from auth.tokens import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from settings import settings


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    # 32+ bytes avoids PyJWT InsecureKeyLengthWarning and matches production guidance.
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-unit-tests-32bytes!!")


def test_create_and_decode_access_token_round_trip():
    token = create_access_token(1, "ops@example.com", "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "ops@example.com"
    assert payload["role"] == "admin"


def test_decode_access_token_rejects_bad_signature():
    token = create_access_token(1, "ops@example.com", "admin")
    header, payload, _signature = token.split(".")
    tampered = f"{header}.{payload}.not-a-valid-signature"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_decode_access_token_rejects_expired(monkeypatch):
    monkeypatch.setattr(settings, "jwt_access_token_minutes", -1)
    token = create_access_token(1, "ops@example.com", "admin")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_generate_refresh_token_is_unique_and_long():
    a = generate_refresh_token()
    b = generate_refresh_token()
    assert a != b
    assert len(a) > 32


def test_hash_refresh_token_is_deterministic_and_one_way():
    token = generate_refresh_token()
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != token
