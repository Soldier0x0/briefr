"""Tests for database URL resolution."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.config import database_backend, resolve_database_url


def test_missing_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("db.config.settings.database_url", "", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        resolve_database_url()


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
