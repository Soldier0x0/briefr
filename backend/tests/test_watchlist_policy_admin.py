"""Admin watchlist policy GET/PUT."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "watchlist-policy.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_watchlist_policy_defaults_and_round_trip(admin_client):
    res = admin_client.get("/api/admin/watchlist/policy")
    assert res.status_code == 200
    body = res.json()
    assert body["triggers"]["kev"] is True
    assert body["triggers"]["patch"] is False
    assert body["delivery"] == "immediate"

    updated = admin_client.put(
        "/api/admin/watchlist/policy",
        json={"triggers": {"patch": True, "epss": False}},
    )
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["triggers"]["patch"] is True
    assert saved["triggers"]["epss"] is False
    assert saved["triggers"]["kev"] is True

    again = admin_client.get("/api/admin/watchlist/policy")
    assert again.json()["triggers"]["patch"] is True
