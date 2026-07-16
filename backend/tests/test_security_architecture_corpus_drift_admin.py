"""PM-3d: admin corpus drift diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from security_architecture.corpus_drift import check_corpus_drift


def test_check_corpus_drift_matches_committed_files():
    result = check_corpus_drift()
    assert result["ok"] is True
    assert result["drifted_files"] == []
    assert "generate_security_corpus.py" in result["regenerate_command"]


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "corpus_drift.db"
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


def test_admin_corpus_drift_endpoint(admin_client):
    res = admin_client.post("/api/admin/diagnostics/corpus-drift")
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["drifted_files"] == []
