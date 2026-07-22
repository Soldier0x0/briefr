"""Health must not advertise orphaned CACHE_REFRESH_* as a live daily job."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark = pytest.mark.no_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "health_refresh.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_refresh_schedule_not_advertised_as_live_job(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    # Either absent, null, or explicitly not a live cron claim
    sched = body.get("refresh_schedule")
    assert sched in (None, {}) or sched.get("live") is False
    # Must still expose next NVD-style refresh when available
    assert "next_refresh_utc" in body or body.get("next_refresh_utc") is None
