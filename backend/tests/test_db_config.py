"""Tests for database URL resolution."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.config import database_backend, resolve_database_url


def test_default_url_uses_db_path(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setattr(
        "db.config.settings.database_url",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        "db.config.settings.db_path",
        "",
        raising=False,
    )
    assert resolve_database_url() == "sqlite+aiosqlite:////tmp/custom.db"
    assert database_backend() == "sqlite"


def test_postgres_url_detected(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://briefr:secret@localhost:5432/briefr",
    )
    monkeypatch.setattr(
        "db.config.settings.database_url",
        "postgresql://briefr:secret@localhost:5432/briefr",
        raising=False,
    )
    assert database_backend() == "postgresql"
