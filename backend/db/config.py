"""Database URL resolution and backend detection."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from settings import settings

_SQLITE_DEFAULT_PATH = os.environ.get("DB_PATH", "briefr.db")


def resolve_database_url() -> str:
    """Return the effective database URL.

  Priority:
  1. ``DATABASE_URL`` env / settings (explicit)
  2. ``DB_PATH``-derived SQLite URL (legacy default)
    """
    explicit = (settings.database_url or os.environ.get("DATABASE_URL", "")).strip()
    if explicit:
        return explicit
    path = (settings.db_path or _SQLITE_DEFAULT_PATH).strip()
    if path.startswith("sqlite:"):
        return path
    return f"sqlite+aiosqlite:///{path}"


def get_database_url() -> str:
    return resolve_database_url()


def database_backend(url: str | None = None) -> str:
    """``sqlite`` or ``postgresql``."""
    parsed = urlparse(url or resolve_database_url())
    scheme = (parsed.scheme or "").lower()
    if scheme in {"postgres", "postgresql"}:
        return "postgresql"
    if scheme in {"sqlite", "sqlite+aiosqlite"}:
        return "sqlite"
    raise ValueError(
        f"Unsupported DATABASE_URL scheme {scheme!r} — "
        "use sqlite+aiosqlite:///path or postgresql://user:pass@host/db"
    )


def is_postgres(url: str | None = None) -> bool:
    return database_backend(url) == "postgresql"


def is_sqlite(url: str | None = None) -> bool:
    return database_backend(url) == "sqlite"


def postgres_dsn(url: str | None = None) -> str:
    """Normalize to an asyncpg-compatible postgresql:// DSN."""
    raw = url or resolve_database_url()
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if scheme == "postgresql":
        return raw
    if scheme == "postgres":
        return raw.replace("postgres://", "postgresql://", 1)
    raise ValueError("Not a PostgreSQL URL")
