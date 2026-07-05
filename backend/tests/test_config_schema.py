"""Tests for config_schema.py and its wiring into /api/admin/config*."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from config_schema import (
    CONFIG_SCHEMA,
    INTEGER_KEYS,
    RESTART_REQUIRED_KEYS,
    WRITABLE_CONFIG_KEYS,
    get_field,
    list_schema,
    validate_value,
)
from database import init_db


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "config_schema.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async():
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    asyncio.run(init_db())

    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("briefr_at", auth_token())
    return client


def test_no_duplicate_keys_in_schema():
    keys = [f.key for f in CONFIG_SCHEMA]
    assert len(keys) == len(set(keys))


def test_get_field_returns_none_for_unknown_key():
    assert get_field("NOT_A_REAL_KEY") is None


def test_validate_value_enforces_int_bounds():
    assert validate_value("NVD_SYNC_INTERVAL_HOURS", "5") is None
    assert validate_value("NVD_SYNC_INTERVAL_HOURS", "0") is not None  # below min=1
    assert validate_value("NVD_SYNC_INTERVAL_HOURS", "999") is not None  # above max=24
    assert validate_value("NVD_SYNC_INTERVAL_HOURS", "not-a-number") is not None


def test_validate_value_enforces_enum():
    assert validate_value("LOG_FORMAT", "json") is None
    assert validate_value("LOG_FORMAT", "plain") is None
    assert validate_value("LOG_FORMAT", "xml") is not None


def test_validate_value_noop_for_unknown_key():
    # Keys outside the schema aren't validated here — the allowlist check
    # happens separately in the /api/admin/config handlers.
    assert validate_value("NOT_A_SCHEMA_KEY", "anything") is None


def test_validate_value_noop_for_non_enforced_types():
    assert validate_value("BACKUP_DIR", "") is None
    assert validate_value("SCHEDULER_TIMEZONE", "Not/A/Real/Zone") is None


def test_list_schema_shape():
    items = list_schema()
    assert items
    sample = next(f for f in items if f["key"] == "NVD_SYNC_INTERVAL_HOURS")
    assert sample["section"] == "scheduler_main"
    assert sample["type"] == "int"
    assert sample["min"] == 1
    assert sample["max"] == 24
    assert sample["help_text"]


def test_config_schema_endpoint(admin_client):
    resp = admin_client.get("/api/admin/config/schema")
    assert resp.status_code == 200
    data = resp.json()
    keys = {f["key"] for f in data}
    assert "NVD_API_KEY" in keys
    assert "DISCORD_WEBHOOK_URL" in keys
    assert len(data) == len(WRITABLE_CONFIG_KEYS)


def test_set_config_rejects_out_of_range_int(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    resp = admin_client.post("/api/admin/config", json={"key": "DATABASE_POOL_SIZE", "value": "0"})
    assert resp.status_code == 400


def test_set_config_accepts_in_range_int(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    resp = admin_client.post("/api/admin/config", json={"key": "DATABASE_POOL_SIZE", "value": "20"})
    assert resp.status_code == 200


def test_apply_all_rejects_out_of_range_int(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    resp = admin_client.post(
        "/api/admin/config/apply-all",
        json=[{"key": "CIRCUIT_FAILURE_THRESHOLD", "value": "999"}],
    )
    assert resp.status_code == 400
