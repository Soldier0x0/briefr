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
def postgres_migrations():
    """Schema only — do not bind asyncpg pool to a closed event loop."""

    async def _boot() -> None:
        import asyncpg

        from database import run_postgres_migrations
        from db.config import postgres_dsn

        await run_postgres_migrations()
        # Run the same schema fixup init_db() would do, via a direct
        # connection — not get_db()/init_pool(), which would bind the pool
        # to this asyncio.run() loop that's about to close.
        conn = await asyncpg.connect(postgres_dsn(), timeout=15)
        try:
            await conn.execute("UPDATE cves SET epss_score = NULL WHERE epss_score = 0.0")
        finally:
            await conn.close()

    asyncio.run(_boot())


def test_postgres_pool_acquire_query_and_stats(postgres_migrations):
    async def _run() -> None:
        from db.connection import close_pool, get_connection, get_pool_stats, init_pool

        await init_pool()
        try:
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
        finally:
            await close_pool()

    asyncio.run(_run())


def test_postgres_pool_stats_on_health(postgres_migrations, monkeypatch):
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
