"""Cloudflare Access identity from the validated Cf-Access-Jwt-Assertion JWT.

The production instance sits behind a Cloudflare Access policy, so every
edge-routed request carries a `Cf-Access-Jwt-Assertion` JWT signed by the
team domain. This module validates that JWT (signature against the team
JWKS, `aud` tag, issuer, expiry) and only then derives the analyst identity.

The plain `Cf-Access-Authenticated-User-Email` header is NEVER trusted:
the LAN -> nginx path bypasses the Cloudflare edge, so headers are
spoofable there (see docs/THREAT_MODEL.md § Spoofing).

When `CF_ACCESS_TEAM_DOMAIN` / `CF_ACCESS_AUD` are unset (dev/LAN),
identity resolution is disabled and every request's identity is None.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt
from fastapi import Request

from resilient_client import resilient_get

logger = logging.getLogger(__name__)

ASSERTION_HEADER = "Cf-Access-Jwt-Assertion"
JWKS_SOURCE = "cf_access_jwks"
JWKS_TTL_SECONDS = 6 * 3600.0
# Floor between forced refetches so unknown-kid garbage tokens cannot
# turn the JWKS endpoint into a request amplifier.
JWKS_MIN_REFRESH_SECONDS = 60.0

# kid -> verification key; single event loop, plain dict ops are safe.
_jwks_cache: dict[str, Any] = {"keys": {}, "fetched_at": 0.0}


def get_cf_access_config() -> tuple[str, str] | None:
    """Return (team_domain, aud) when CF Access validation is configured."""
    team = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip().rstrip("/")
    aud = os.environ.get("CF_ACCESS_AUD", "").strip()
    if not team or not aud:
        return None
    team = team.removeprefix("https://").removeprefix("http://")
    if "." not in team:
        team = f"{team}.cloudflareaccess.com"
    return team, aud


def reset_jwks_cache() -> None:
    """Test helper — drop cached signing keys."""
    _jwks_cache["keys"] = {}
    _jwks_cache["fetched_at"] = 0.0


def _keys_from_jwks_payload(payload: Any) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    raw_keys = payload.get("keys", []) if isinstance(payload, dict) else []
    for raw in raw_keys:
        if not isinstance(raw, dict):
            continue
        kid = (raw.get("kid") or "").strip()
        if not kid:
            continue
        try:
            keys[kid] = jwt.PyJWK.from_dict(raw).key
        except jwt.exceptions.PyJWKError as exc:
            logger.warning("Skipping unusable JWKS key %s: %s", kid, exc)
    return keys


async def _load_signing_keys(team_domain: str, *, force: bool = False) -> dict[str, Any]:
    """Fetch and cache the team-domain JWKS (kid -> RSA public key)."""
    now = time.time()
    age = now - _jwks_cache["fetched_at"]
    if _jwks_cache["keys"] and not force and age < JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]
    if force and _jwks_cache["fetched_at"] and age < JWKS_MIN_REFRESH_SECONDS:
        return _jwks_cache["keys"]

    response = await resilient_get(
        JWKS_SOURCE,
        f"https://{team_domain}/cdn-cgi/access/certs",
        timeout=10.0,
    )
    _jwks_cache["keys"] = _keys_from_jwks_payload(response.json())
    _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


async def identity_from_token(token: str) -> str | None:
    """Validate a Cf-Access-Jwt-Assertion JWT and return the email claim.

    Returns None (no identity) on any validation failure: bad signature,
    wrong audience, wrong issuer, expired token, unknown signing key.
    """
    config = get_cf_access_config()
    if not config or not token:
        return None
    team_domain, aud = config

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        logger.warning("CF Access JWT unreadable header: %s", exc)
        return None

    kid = (header.get("kid") or "").strip()
    keys = await _load_signing_keys(team_domain)
    key = keys.get(kid)
    if key is None:
        # Key rotation: refetch once (rate-floored) before giving up.
        keys = await _load_signing_keys(team_domain, force=True)
        key = keys.get(kid)
    if key is None:
        logger.warning("CF Access JWT signed with unknown kid %r", kid)
        return None

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=aud,
            issuer=f"https://{team_domain}",
            options={"require": ["exp", "iat"]},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("CF Access JWT rejected: %s", exc)
        return None

    email = (claims.get("email") or "").strip().lower()
    return email or None


async def identity_from_request(request: Request) -> str | None:
    """Resolve the authenticated identity for a request, or None.

    None means: CF Access validation not configured (dev/LAN), no assertion
    header present (LAN path), or the assertion failed validation.
    """
    if get_cf_access_config() is None:
        return None
    token = (request.headers.get(ASSERTION_HEADER) or "").strip()
    if not token:
        return None
    return await identity_from_token(token)
