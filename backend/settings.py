"""Owns process/env Settings (Pydantic BaseSettings); not admin writable keys.

Application settings (V1.2 §5.2 phase 1).

Pydantic BaseSettings for env config. Phase 1 migrates only the variables
main.py read at module import time; per-request `os.environ.get` reads
elsewhere keep their current call-time semantics and move here in later
router-split phases.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Keys present before `.env` load — real process env (systemd, secrets) wins over DB.
PROCESS_ENV_KEYS: frozenset[str] = frozenset(os.environ.keys())

load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    briefr_env: str = "production"
    allowed_origins: str = "http://localhost:3000"
    database_url: str = ""
    db_path: str = ""
    database_pool_size: int = 10
    database_pool_acquire_timeout_seconds: int = 10
    database_pool_command_timeout_seconds: int = 60  # SQL only; not feed HTTP
    briefr_require_postgres: bool = True

    # §5.5 — structured logging + rate limiting (import-time config)
    log_format: str = "json"
    rate_limit_enabled: bool = True
    rate_limit_ioc_per_minute: int = 30
    rate_limit_refresh_per_minute: int = 10
    rate_limit_admin_read_per_minute: int = 120
    rate_limit_wallboard_per_minute: int = 60

    # V1.4 Theme 4 — optional read-only kiosk token (X-BRIEFR-Wallboard-Token).
    wallboard_token: str = ""
    # Issue #843 — auto-rotate kiosk token + authenticated issuance endpoint.
    wallboard_auto_token: bool = False
    wallboard_token_rotation_hours: int = 24
    wallboard_issuance_token_minutes: int = 5

    # Built-in app login (decision 2026-06-11) — the only auth mechanism.
    jwt_secret: str = ""
    jwt_access_token_minutes: int = 15
    refresh_token_days: int = 30
    auth_cookie_secure: bool = True
    rate_limit_login_per_minute: int = 5
    rate_limit_auth_refresh_per_minute: int = 30
    # Embeddings E5 — stricter than interactive session for Bearer search tokens
    rate_limit_search_token_per_minute: int = 30

    @field_validator("briefr_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("wallboard_token")
    @classmethod
    def _strip_wallboard_token(cls, value: str) -> str:
        return value.strip()

    @field_validator("jwt_secret")
    @classmethod
    def _strip_jwt_secret(cls, value: str) -> str:
        return value.strip()

    @field_validator("database_url", "db_path")
    @classmethod
    def _strip_db_settings(cls, value: str) -> str:
        return value.strip()

    @field_validator("log_format")
    @classmethod
    def _normalize_log_format(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.briefr_env == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()

# Fail closed in production BEFORE any auto-generation: a production box must
# provide JWT_SECRET explicitly. Auto-generating here would (a) make this guard
# dead code and (b) mint a different per-replica secret, silently invalidating
# sessions across replicas / ephemeral containers. This check must stay ahead of
# the dev/test auto-generation block below.
if settings.is_production and not settings.jwt_secret:
    raise RuntimeError(
        "JWT_SECRET must be set in production (generate with `openssl rand -hex 32`)"
    )

if not settings.jwt_secret:
    # Dev/test only: first boot with no JWT_SECRET set — generate one and persist
    # it to .env so it survives restarts (same dotenv.set_key() mechanism
    # routers/admin.py uses for runtime-writable config) instead of forcing a
    # manual step. Never reached in production (guarded above).
    _generated_secret = secrets.token_hex(32)
    _dotenv_path = Path(__file__).resolve().parent / ".env"
    try:
        set_key(str(_dotenv_path), "JWT_SECRET", _generated_secret)
    except OSError:
        logger.warning(
            "No JWT_SECRET configured — generated one in-memory but could not "
            "persist it to .env; it will change on restart until set explicitly"
        )
    else:
        logger.warning("No JWT_SECRET configured — generated and persisted a new one to .env")
    os.environ["JWT_SECRET"] = _generated_secret
    settings.jwt_secret = _generated_secret


def production_posture_warnings(config: Settings = settings) -> list[dict[str, str]]:
    """Unsafe-flag report for production posture (Sprint A6).

    Each entry: {"flag": <env var name>, "message": <operator-facing text>}.
    Computed from current settings regardless of environment so the admin
    Security panel can show posture anywhere; main.py logs the warnings at
    startup only when is_production.
    """
    warnings: list[dict[str, str]] = []
    if not config.rate_limit_enabled:
        warnings.append({
            "flag": "RATE_LIMIT_ENABLED=0",
            "message": (
                "IOC, refresh, admin, wallboard, and auth endpoints are not "
                "throttled. Set RATE_LIMIT_ENABLED=1."
            ),
        })
    if not config.auth_cookie_secure:
        warnings.append({
            "flag": "AUTH_COOKIE_SECURE=0",
            "message": (
                "Auth cookies are sent over plain HTTP and can be intercepted. "
                "Set AUTH_COOKIE_SECURE=1 behind HTTPS."
            ),
        })
    if not config.wallboard_token:
        warnings.append({
            "flag": "WALLBOARD_TOKEN unset",
            "message": (
                "/api/wallboard is readable without a token. Set "
                "WALLBOARD_TOKEN to require X-BRIEFR-Wallboard-Token."
            ),
        })
    return warnings
