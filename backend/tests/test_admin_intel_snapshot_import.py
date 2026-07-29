"""Admin intel snapshot import path policy tests."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "intel.db"
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


def test_intel_snapshot_import_rejects_path_outside_allowlist(admin_client, tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    bundle = outside / "briefr-intel-demo.pgdump.gz"
    bundle.write_bytes(b"test")
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    resp = admin_client.post(
        "/api/admin/intel-snapshot/import",
        json={
            "confirm_text": "import",
            "mode": "merge",
            "input_path": str(bundle),
            "database_url": "postgresql://briefr:briefr@127.0.0.1:5432/briefr",
        },
    )
    assert resp.status_code == 400
    assert "must be under" in resp.json()["detail"]


def test_intel_snapshot_import_accepts_allowed_bundle(admin_client, tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    bundle = allowed / "briefr-intel-demo.pgdump.gz"
    bundle.write_bytes(b"test")
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    with patch("routers.admin.intel_snapshot._run_import"):
        resp = admin_client.post(
            "/api/admin/intel-snapshot/import",
            json={
                "confirm_text": "import",
                "mode": "merge",
                "input_path": str(bundle),
                "database_url": "postgresql://briefr:briefr@127.0.0.1:5432/briefr",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
