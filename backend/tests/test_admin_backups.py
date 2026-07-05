"""Tests for /api/admin/backups/* endpoints."""

import asyncio
import io
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "backup.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    # Disable rate limiting so tests don't hit 429
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("briefr_at", auth_token())
    return client


def test_list_backups_returns_200(admin_client):
    resp = admin_client.get("/api/admin/backups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_run_backup_returns_ok(admin_client, tmp_path):
    fake_result = {
        "status": "ok",
        "archive": str(tmp_path / "briefr-20260101T000000Z.tar.gz"),
        "encrypted": False,
        "reason": "manual-admin",
        "pruned": [],
        "retention": 100,
    }
    with patch("backup.manager.run_backup", return_value=fake_result):
        resp = admin_client.post("/api/admin/backups/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "filename" in data
    assert "size_bytes" in data


def test_upload_path_traversal_rejected(admin_client, tmp_path):
    data = b"fake content"
    resp = admin_client.post(
        "/api/admin/backups/upload",
        files={"file": ("../evil.tar.gz", io.BytesIO(data), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_upload_bad_pattern_rejected(admin_client, tmp_path):
    data = b"fake content"
    resp = admin_client.post(
        "/api/admin/backups/upload",
        files={"file": ("notbriefr-test.tar.gz", io.BytesIO(data), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_upload_valid_filename_accepted(admin_client, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("routers.admin.BACKUP_DIR", str(backup_dir))

    data = b"fake archive content"
    resp = admin_client.post(
        "/api/admin/backups/upload",
        files={"file": ("briefr-2026-01-01.tar.gz", io.BytesIO(data), "application/octet-stream")},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["ok"] is True
    assert result["filename"] == "briefr-2026-01-01.tar.gz"


def test_verify_endpoint_reads_manifest(admin_client, tmp_path, monkeypatch):
    """Verify reads manifest.json from archive without full extraction."""
    import json
    import tarfile

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("routers.admin.BACKUP_DIR", str(backup_dir))

    # Create a valid .tar.gz with a manifest.json
    archive_path = backup_dir / "briefr-test-verify.tar.gz"
    manifest = {"integrity": "ok", "reason": "test", "db_size": 12345}

    with tarfile.open(archive_path, "w:gz") as tar:
        manifest_bytes = json.dumps(manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))

    resp = admin_client.post(
        f"/api/admin/backups/verify/{archive_path.name}",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "manifest" in data["details"] or "integrity=ok" in data["details"]


def test_verify_nonexistent_file_returns_404(admin_client, tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("routers.admin.BACKUP_DIR", str(backup_dir))

    resp = admin_client.post("/api/admin/backups/verify/briefr-does-not-exist.tar.gz", json={})
    assert resp.status_code == 404


def test_upload_path_traversal_stays_in_backup_dir(admin_client, tmp_path, monkeypatch):
    """Path traversal in filename must be rejected — filename stays within BACKUP_DIR."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("routers.admin.BACKUP_DIR", str(backup_dir))

    # Try to write outside the backup_dir
    data = b"malicious content"
    resp = admin_client.post(
        "/api/admin/backups/upload",
        files={"file": ("../evil-file.tar.gz", io.BytesIO(data), "application/octet-stream")},
    )
    assert resp.status_code == 400  # Must reject path traversal
