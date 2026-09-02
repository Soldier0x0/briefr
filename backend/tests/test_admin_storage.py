"""Tests for /api/admin/storage endpoints — disk usage, purge, export."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _postgres_is_live



@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    # Use the real Postgres database (migrations applied by _postgres_schema_once)
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
    assert data["backup_partition"]["path"] != data["db_partition"]["path"] or (
        data["db_partition"]["device_id"] is not None
        and data["backup_partition"]["device_id"] == data["db_partition"]["device_id"]
    )


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


def test_storage_export_returns_sql_file(admin_client, monkeypatch):
    async def fake_dump(tmp_path):
        tmp_path.write_text("-- BRIEFR dump\n")

    monkeypatch.setattr("routers.admin.storage._run_export_dump", fake_dump)

    resp = admin_client.get("/api/admin/storage/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers.get("content-type", "").startswith("application/sql")
    assert b"-- BRIEFR dump" in resp.content


def test_resources_reuses_held_connection(admin_client, monkeypatch):
    calls = {"n": 0}

    async def counting_get_db():
        calls["n"] += 1
        if calls["n"] > 1:
            raise AssertionError("nested get_db")
        from database import get_db as _get_db
        return await _get_db()

    async def fake_fetch(db, window):
        return {"ok": True, "window": window}

    monkeypatch.setattr("routers.admin.storage.get_db", counting_get_db)
    monkeypatch.setattr(
        "db.resource_metrics.fetch_resources_response", fake_fetch
    )

    resp = admin_client.get("/api/admin/resources")
    assert resp.status_code == 200
    assert calls["n"] == 1


@pytest.mark.skipif(
    not _postgres_is_live(),
    reason="requires live Postgres (pg_class app/intel table sizes)",
)
def test_fetch_table_sizes_includes_app_or_intel():
    from database import get_db
    from storage_metrics import fetch_table_sizes
    from tests.conftest import run_db_test

    async def _run():
        db = await get_db()
        try:
            rows = await fetch_table_sizes(db)
            names = {r["table"] for r in rows}
            assert "api_call_events" in names or "cves" in names
            assert "procrastinate_jobs" not in names  # default exclude system
            for row in rows:
                assert "schema" in row
                assert "table" in row
                assert "size_bytes" in row
                assert row["schema"] in ("app", "intel")
            with_system = await fetch_table_sizes(db, include_system=True)
            system_names = {r["table"] for r in with_system}
            assert "procrastinate_jobs" in system_names or any(
                r["schema"] == "public" for r in with_system
            )
        finally:
            await db.close()

    run_db_test(_run())


@pytest.mark.skipif(
    not _postgres_is_live(),
    reason="requires live Postgres (pg_class app/intel table sizes and COUNT)",
)
def test_storage_table_sizes_include_row_counts(admin_client):
    resp = admin_client.get("/api/admin/storage")
    assert resp.status_code == 200
    data = resp.json()
    sizes = data["table_sizes"]
    assert isinstance(sizes, list)
    names = {r["table"] for r in sizes}
    assert "api_call_events" in names or "cves" in names
    assert "procrastinate_jobs" not in names
    target = next(
        (r for r in sizes if r["table"] in ("api_call_events", "cves")),
        None,
    )
    assert target is not None
    assert target["schema"] in ("app", "intel")
    assert isinstance(target.get("rows"), int)
    assert target["rows"] >= 0
    tables = data["tables"]
    assert tables[target["table"]] == target["rows"]
