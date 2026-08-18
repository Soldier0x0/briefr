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


def issue_session_token(*, generation: int = 0) -> str:
    exp = int(time.time()) + TTL_SECONDS
    nonce = secrets.token_hex(16)
    payload = f"{nonce}.{exp}.{generation}"
    sig = hmac.new(_signing_key().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str, *, expected_generation: int | None = None) -> bool:
    parts = (token or "").split(".")
    if len(parts) not in (3, 4):
        return False
    if expected_generation is not None and expected_generation > 0 and len(parts) == 3:
        return False
    if len(parts) == 3:
        nonce, exp_s, sig = parts
        generation = 0
    else:
        nonce, exp_s, gen_s, sig = parts
        try:
            generation = int(gen_s)
        except ValueError:
            return False
        if expected_generation is not None and generation != expected_generation:
            return False
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        return False
    payload = f"{nonce}.{exp_s}" if len(parts) == 3 else f"{nonce}.{exp_s}.{gen_s}"
    expected = hmac.new(_signing_key().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


async def wallboard_token_matches(provided: str) -> bool:
    from wallboard.token_store import token_matches_configured, verify_issuance_token

    if not provided:
        return False
    generation = 0
    if settings.wallboard_auto_token:
        from wallboard.token_store import get_token_generation

        generation = await get_token_generation()
        if verify_issuance_token(provided, expected_generation=generation):
            return True
    return await token_matches_configured(provided)
