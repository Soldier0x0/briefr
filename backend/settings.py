"""Application settings (V1.2 §5.2 phase 1).

Pydantic BaseSettings for env config. Phase 1 migrates only the variables
main.py read at module import time; per-request `os.environ.get` reads
elsewhere keep their current call-time semantics and move here in later
router-split phases.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    briefr_env: str = "development"
    briefr_admin_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"
    database_url: str = ""
    db_path: str = ""
    database_pool_size: int = 10
    briefr_require_postgres: bool = False

    # §5.5 — structured logging + rate limiting (import-time config)
    log_format: str = "json"
    rate_limit_enabled: bool = True
    rate_limit_ioc_per_minute: int = 30
    rate_limit_refresh_per_minute: int = 10
    rate_limit_wallboard_per_minute: int = 60

    # V1.4 Theme 4 — optional read-only kiosk token (X-BRIEFR-Wallboard-Token).
    wallboard_token: str = ""

    # Built-in app login (decision 2026-06-11) — replaces X-BRIEFR-Admin-Key.
    jwt_secret: str = ""
    jwt_access_token_minutes: int = 15
    refresh_token_days: int = 30
    auth_cookie_secure: bool = True
    allow_legacy_admin_key: bool = True
    rate_limit_login_per_minute: int = 5
    rate_limit_auth_refresh_per_minute: int = 30

    @field_validator("briefr_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("briefr_admin_api_key")
    @classmethod
    def _strip_admin_key(cls, value: str) -> str:
        return value.strip()

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

if not settings.jwt_secret:
    # First boot with no JWT_SECRET set: generate one and persist it to .env
    # so it survives restarts (same dotenv.set_key() mechanism routers/admin.py
    # uses for runtime-writable config) instead of forcing a manual step.
    _generated_secret = secrets.token_hex(32)
    _dotenv_path = Path(__file__).resolve().parent / ".env"
    try:
        set_key(str(_dotenv_path), "JWT_SECRET", _generated_secret)
    except OSError:
        pass
    os.environ["JWT_SECRET"] = _generated_secret
    settings.jwt_secret = _generated_secret
    logger.warning("No JWT_SECRET configured — generated and persisted a new one to .env")

if settings.is_production and not settings.jwt_secret:
    raise RuntimeError(
        "JWT_SECRET must be set in production (generate with `openssl rand -hex 32`)"
    )
