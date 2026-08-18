"""Wallboard token rotation, issuance JWTs, and revocation (issue #843).

Active kiosk tokens are stored encrypted in ``app_settings`` when auto-rotation
is enabled. Short-lived issuance JWTs (audience ``wallboard``) let authenticated
analysts bootstrap a kiosk session without typing ``WALLBOARD_TOKEN``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt

from database import get_db
from db.app_settings import get_app_setting, set_app_setting
from settings import settings
from settings_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

GEN_KEY = "wallboard.token_generation"
ROTATED_TOKEN_KEY = "wallboard.rotated_token"
LAST_ROTATION_KEY = "wallboard.last_rotation_at"

AUDIENCE = "briefr-wallboard"
ISSUANCE_PREFIX = "wbiss."

_generation_cache: int | None = None
_rotated_token_cache: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_generation(db) -> int:
    global _generation_cache
    raw = await get_app_setting(db, GEN_KEY)
    try:
        generation = int(raw or "0")
    except ValueError:
        generation = 0
    _generation_cache = generation
    return generation


async def get_token_generation() -> int:
    if _generation_cache is not None:
        return _generation_cache
    db = await get_db()
    try:
        return await _load_generation(db)
    finally:
        await db.close()


async def _load_rotated_token(db) -> str:
    global _rotated_token_cache
    stored = await get_app_setting(db, ROTATED_TOKEN_KEY)
    if not stored:
        _rotated_token_cache = ""
        return ""
    try:
        token = decrypt_secret(stored)
    except ValueError:
        logger.warning("Failed to decrypt wallboard.rotated_token — treating as unset")
        token = ""
    _rotated_token_cache = token
    return token


async def get_effective_wallboard_token() -> str:
    """Token used to gate wallboard access (manual env or rotated store)."""
    if not settings.wallboard_auto_token:
        return settings.wallboard_token or ""
    if _rotated_token_cache is not None:
        return _rotated_token_cache or settings.wallboard_token or ""
    db = await get_db()
    try:
        rotated = await _load_rotated_token(db)
        return rotated or settings.wallboard_token or ""
    finally:
        await db.close()


def _invalidate_caches() -> None:
    global _generation_cache, _rotated_token_cache
    _generation_cache = None
    _rotated_token_cache = None


def token_digest(token: str) -> bytes:
    return hashlib.sha256((token or "").encode()).digest()


async def token_matches_configured(provided: str) -> bool:
    configured = await get_effective_wallboard_token()
    if not configured:
        return False
    return secrets.compare_digest(token_digest(provided), token_digest(configured))


def issue_issuance_token(*, username: str, generation: int) -> tuple[str, datetime]:
    """Return a short-lived scoped JWT for wallboard session bootstrap."""
    now = _now()
    exp = now + timedelta(minutes=max(1, settings.wallboard_issuance_token_minutes))
    payload = {
        "sub": username,
        "aud": AUDIENCE,
        "iat": now,
        "exp": exp,
        "gen": generation,
        "typ": "wallboard_issuance",
    }
    secret = settings.jwt_secret or settings.wallboard_token or "briefr-wallboard-dev"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return f"{ISSUANCE_PREFIX}{token}", exp


def verify_issuance_token(token: str, *, expected_generation: int) -> bool:
    if not token or not token.startswith(ISSUANCE_PREFIX):
        return False
    raw = token[len(ISSUANCE_PREFIX) :]
    secret = settings.jwt_secret or settings.wallboard_token or "briefr-wallboard-dev"
    try:
        payload = jwt.decode(
            raw,
            secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            options={"require": ["exp", "iat", "sub", "gen"]},
        )
    except jwt.PyJWTError:
        return False
    if payload.get("typ") != "wallboard_issuance":
        return False
    try:
        generation = int(payload.get("gen") or -1)
    except (TypeError, ValueError):
        return False
    return generation == expected_generation


async def rotate_wallboard_token(*, actor: str | None = None) -> dict:
    """Generate a new kiosk token, persist encrypted, bump generation."""
    new_token = secrets.token_urlsafe(32)
    now = _now()
    db = await get_db()
    try:
        generation = await _load_generation(db) + 1
        encrypted = encrypt_secret(new_token)
        if encrypted is None:
            # No BRIEFR_SETTINGS_KEY — store plaintext (legacy) but still rotate.
            encrypted = new_token
        await set_app_setting(db, GEN_KEY, str(generation))
        await set_app_setting(db, ROTATED_TOKEN_KEY, encrypted)
        await set_app_setting(db, LAST_ROTATION_KEY, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        await db.commit()
    finally:
        await db.close()
    _invalidate_caches()
    logger.info(
        "Wallboard token rotated (generation=%s, actor=%s)",
        generation,
        actor or "scheduler",
    )
    return {
        "generation": generation,
        "rotated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def revoke_wallboard_tokens(*, actor: str | None = None) -> dict:
    """Invalidate all issuance JWTs and session cookies by bumping generation."""
    db = await get_db()
    try:
        generation = await _load_generation(db) + 1
        await set_app_setting(db, GEN_KEY, str(generation))
        await set_app_setting(db, LAST_ROTATION_KEY, _now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        await db.commit()
    finally:
        await db.close()
    _invalidate_caches()
    logger.info("Wallboard tokens revoked (generation=%s, actor=%s)", generation, actor or "admin")
    return {"generation": generation}


async def ensure_rotated_token_seeded() -> None:
    """On startup with auto-token enabled, seed rotated token from env if missing."""
    if not settings.wallboard_auto_token:
        return
    db = await get_db()
    try:
        existing = await get_app_setting(db, ROTATED_TOKEN_KEY)
        if existing:
            return
        seed = settings.wallboard_token or secrets.token_urlsafe(32)
        encrypted = encrypt_secret(seed)
        if encrypted is None:
            encrypted = seed
        await set_app_setting(db, ROTATED_TOKEN_KEY, encrypted)
        await set_app_setting(db, GEN_KEY, "1")
        await set_app_setting(db, LAST_ROTATION_KEY, _now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        await db.commit()
    finally:
        await db.close()
    _invalidate_caches()


async def rotation_status() -> dict:
    db = await get_db()
    try:
        generation = await _load_generation(db)
        last_rotation = await get_app_setting(db, LAST_ROTATION_KEY)
        has_rotated = bool(await get_app_setting(db, ROTATED_TOKEN_KEY))
    finally:
        await db.close()
    return {
        "auto_token_enabled": settings.wallboard_auto_token,
        "generation": generation,
        "last_rotation_at": last_rotation,
        "has_rotated_token": has_rotated,
        "rotation_interval_hours": settings.wallboard_token_rotation_hours,
        "issuance_token_minutes": settings.wallboard_issuance_token_minutes,
    }


def issuance_not_before() -> float:
    """Monotonic timestamp for rate-limit spacing (module-level noop helper)."""
    return time.time()
