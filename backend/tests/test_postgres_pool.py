"""PostgreSQL pool integration tests — run in CI with a live DATABASE_URL."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


@pytest.fixture(scope="module")
def postgres_ready():
    async def _boot() -> None:
        from database import init_db, run_postgres_migrations
        from db.connection import close_pool, init_pool

        await run_postgres_migrations()
        await init_pool()
        await init_db()

    asyncio.run(_boot())
    yield
    asyncio.run(_close())


async def _close() -> None:
    from db.connection import close_pool

    await close_pool()


def test_postgres_pool_acquire_query_and_stats(postgres_ready):
    async def _run() -> None:
        from db.connection import get_connection, get_pool_stats

        db = await get_connection()
        try:
            rows = await db.execute_fetchall("SELECT 1 AS ok")
            assert rows[0]["ok"] == 1
        finally:
            await db.close()

        stats = get_pool_stats()
        assert stats is not None
        assert stats["max"] >= 1
        assert stats["idle"] >= 1
        assert stats["in_use"] == stats["size"] - stats["idle"]

    asyncio.run(_run())


def test_postgres_pool_stats_on_health(postgres_ready, monkeypatch):
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/health")
    assert res.status_code == 200
    pool = res.json()["database"].get("pool")
    assert pool is not None
    assert "idle" in pool
    assert "max" in pool
