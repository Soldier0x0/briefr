"""JWT access tokens + opaque refresh tokens for built-in app login.

Access tokens are stateless JWTs (cheap per-request verification). Refresh
tokens are opaque random strings; only their SHA-256 hash is ever persisted
(see auth/repo.py's `sessions` table) so a DB leak doesn't hand out usable
tokens.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from settings import settings

ALGORITHM = "HS256"


def create_access_token(user_id: int, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (bad signature, expired, malformed) on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
