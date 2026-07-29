"""Tests for /api/admin/storage endpoints — disk usage, purge, export."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

# GET /api/admin/storage/export streams a `VACUUM INTO`'d SQLite file —
# a SQLite-only feature (Postgres backups go through pg_dump, a separate
# script). Not a fixture-pattern gap; the Postgres equivalent is a real
# product feature, Post-B scope, not this CI-gate PR's.
_requires_sqlite = pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="storage export streams a VACUUM INTO SQLite file, no Postgres equivalent yet",
)



@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "storage.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_storage_returns_partition_info(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    assert "db_partition" in data
    assert "backup_partition" in data
    assert "table_sizes" in data
    assert "growth_estimate" in data
    assert "disk_io" in data
    db_part = data["db_partition"]
    assert "total" in db_part
    assert "free" in db_part
    assert "used" in db_part


def test_storage_partition_includes_path_and_device(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["db_partition"]["path"]
    assert "device_id" in data["db_partition"]
    assert data["backup_partition"]["path"]


def test_storage_disk_total_nonzero(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    db_part = data["db_partition"]
    assert db_part["total"] > 0, "disk_total must be non-zero (NaN bug fix)"


def test_storage_disk_pct_not_nan(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    db_part = data["db_partition"]
    total = db_part["total"]
    used = db_part["used"]
    assert total > 0
    pct = used / total * 100
    assert pct == pct  # NaN check: NaN != NaN


def test_storage_returns_table_sizes_and_growth(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    assert "table_sizes" in data
    assert isinstance(data["table_sizes"], list)
    assert "growth_estimate" in data
    assert "disk_io" in data
    assert "available" in data["disk_io"]


def test_purge_ioc_cache_requires_confirm(admin_client):
    resp = admin_client.post("/api/admin/storage/purge", json={"target": "ioc_cache", "confirm_text": "wrong"})
    assert resp.status_code == 400


def test_purge_ioc_cache_succeeds(admin_client):
    resp = admin_client.post(
        "/api/admin/storage/purge",
        json={"target": "ioc_cache", "confirm_text": "clear"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "rows_deleted" in data


def test_purge_feed_cache_requires_clear(admin_client):
    resp = admin_client.post("/api/admin/storage/purge", json={"target": "feed_cache", "confirm_text": "delete"})
    assert resp.status_code == 400


def test_purge_epss_history_requires_prune(admin_client):
    resp = admin_client.post(
        "/api/admin/storage/purge",
        json={"target": "epss_history_old", "confirm_text": "prune"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_purge_unknown_target_returns_400(admin_client):
    resp = admin_client.post(
        "/api/admin/storage/purge",
        json={"target": "nonexistent_table", "confirm_text": "clear"},
    )
    assert resp.status_code == 400


def test_purge_epss_backfill_reset_no_confirm(admin_client):
    """epss_backfill_reset target requires no confirm_text."""
    resp = admin_client.post(
        "/api/admin/storage/purge",
        json={"target": "epss_backfill_reset", "confirm_text": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


@_requires_sqlite
def test_storage_export_returns_file(admin_client):
    resp = admin_client.get("/api/admin/storage/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
