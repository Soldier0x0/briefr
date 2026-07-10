"""Shared rate-limit store (Track I Phase 3b)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rate_limit import TokenBucket
from rate_limit_store import shared_acquire, shared_store_enabled


def test_shared_store_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BRIEFR_RATE_LIMIT_STORE", raising=False)
    assert shared_store_enabled() is False


def test_shared_store_enabled_with_db_flag(monkeypatch):
    monkeypatch.setenv("BRIEFR_RATE_LIMIT_STORE", "db")
    assert shared_store_enabled() is True


def test_shared_acquire_persists_across_buckets(tmp_path, monkeypatch):
    from database import init_db
    import asyncio

    db_path = tmp_path / "rl_store.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BRIEFR_RATE_LIMIT_STORE", "db")
    from settings import settings

    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    asyncio.run(init_db())

    bucket = TokenBucket(2, name="test_shared")
    assert bucket.acquire("client-a") == 0.0
    assert bucket.acquire("client-a") == 0.0
    retry = bucket.acquire("client-a")
    assert retry > 0.0

    bucket2 = TokenBucket(2, name="test_shared")
    retry2 = bucket2.acquire("client-a")
    assert retry2 > 0.0
