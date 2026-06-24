"""Health endpoint probes (live vs full readiness)."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "health.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    from database import init_db
    from fastapi.testclient import TestClient
    from main import app

    asyncio.run(init_db())

    with TestClient(app) as test_client:
        yield test_client


def test_health_live_does_not_touch_database(client):
    res = client.get("/api/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_pool_exhausted_returns_503(client, monkeypatch):
    from db.connection import PoolExhaustedError

    async def _saturated():
        raise PoolExhaustedError("PostgreSQL pool saturated (test)")

    monkeypatch.setattr("database.get_connection", _saturated)

    res = client.get("/api/health")
    assert res.status_code == 503
    assert "saturated" in res.json()["detail"].lower()
