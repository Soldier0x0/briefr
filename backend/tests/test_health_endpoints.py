"""Health endpoint probes (live vs full readiness)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "health.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from fastapi.testclient import TestClient
    from main import app

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

    monkeypatch.setattr("db.init.get_connection", _saturated)

    res = client.get("/api/health")
    assert res.status_code == 503
    # Detail is a fixed, safe message — the real exception stays in the log
    # only (Sprint A4), never echoed back to the client.
    assert res.json()["detail"] == "Server is busy — please retry in a few seconds."
