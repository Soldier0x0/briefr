"""Application settings (V1.2 §5.2 phase 1).

Pydantic BaseSettings for env config. Phase 1 migrates only the variables
main.py read at module import time; per-request `os.environ.get` reads
elsewhere keep their current call-time semantics and move here in later
router-split phases.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    briefr_env: str = "development"
    briefr_admin_api_key: str = ""
    allowed_origins: str = "http://localhost:3000"

    # §5.5 — structured logging + rate limiting (import-time config)
    log_format: str = "json"
    rate_limit_enabled: bool = True
    rate_limit_ioc_per_minute: int = 30
    rate_limit_refresh_per_minute: int = 10

    @field_validator("briefr_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("briefr_admin_api_key")
    @classmethod
    def _strip_admin_key(cls, value: str) -> str:
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
