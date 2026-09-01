"""Owns DATABASE_URL resolution — PostgreSQL only."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from settings import settings


def resolve_database_url() -> str:
    """Return the effective PostgreSQL DSN.

    ``DATABASE_URL`` is required. SQLite is not supported.
    """
    explicit = (settings.database_url or os.environ.get("DATABASE_URL", "")).strip()
    if not explicit:
        raise ValueError(
            "DATABASE_URL is required — set a postgresql:// DSN. "
            "See docs/SELF_HOST.md for Postgres + pgvector setup."
        )
    database_backend(explicit)
    return explicit


def get_database_url() -> str:
    return resolve_database_url()


def database_backend(url: str | None = None) -> str:
    """Always ``postgresql`` once the DSN is valid."""
    parsed = urlparse(url or resolve_database_url())
    scheme = (parsed.scheme or "").lower()
    if scheme in {"postgres", "postgresql"}:
        return "postgresql"
    raise ValueError(
        f"Unsupported DATABASE_URL scheme {scheme!r} — "
        "BRIEFR requires postgresql:// (with pgvector/pgvector:pg16). "
        "See docs/SELF_HOST.md"
    )


def is_postgres(url: str | None = None) -> bool:
    return database_backend(url) == "postgresql"


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
