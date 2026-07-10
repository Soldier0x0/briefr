"""Signed httpOnly wallboard session cookies — never stores raw WALLBOARD_TOKEN."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from settings import settings

COOKIE_NAME = "briefr_wb"
TTL_SECONDS = 30 * 86400


def _signing_key() -> str:
    return settings.jwt_secret or settings.wallboard_token or "briefr-wallboard-dev"


def issue_session_token() -> str:
    exp = int(time.time()) + TTL_SECONDS
    nonce = secrets.token_hex(16)
    payload = f"{nonce}.{exp}"
    sig = hmac.new(_signing_key().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str) -> bool:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return False
    nonce, exp_s, sig = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        return False
    payload = f"{nonce}.{exp_s}"
    expected = hmac.new(_signing_key().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def wallboard_token_matches(provided: str) -> bool:
    configured = settings.wallboard_token or ""
    if not configured:
        return False
    return secrets.compare_digest(
        hashlib.sha256((provided or "").encode()).digest(),
        hashlib.sha256(configured.encode()).digest(),
    )
