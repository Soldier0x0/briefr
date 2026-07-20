"""Tests for config_schema.py and its wiring into /api/admin/config*."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from config_schema import (
    APPLY_IMMEDIATE,
    APPLY_RESTART,
    APPLY_SCHEDULER_RESCHEDULE,
    CONFIG_SCHEMA,
    INTEGER_KEYS,
    RESTART_REQUIRED_KEYS,
    SCHEDULER_RESCHEDULE_KEYS,
    WRITABLE_CONFIG_KEYS,
    get_field,
    list_schema,
    resolved_apply_strategy,
    validate_value,
)


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "config_schema.db"
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
    assert sample["apply_strategy"] == APPLY_SCHEDULER_RESCHEDULE
    assert sample["display_label"] == "NVD sync interval"
    assert sample["unit"] == "h"


@pytest.mark.parametrize(
    "key,expected_strategy",
    [
        ("NVD_API_KEY", APPLY_IMMEDIATE),
        ("WALLBOARD_TOKEN", APPLY_RESTART),
        ("NVD_SYNC_INTERVAL_HOURS", APPLY_SCHEDULER_RESCHEDULE),
        ("DATABASE_POOL_SIZE", APPLY_RESTART),
        ("ALLOWED_ORIGINS", APPLY_RESTART),
        ("MAX_CVES_PER_FETCH", APPLY_IMMEDIATE),
        ("CACHE_REFRESH_HOUR", APPLY_IMMEDIATE),
    ],
)
def test_resolved_apply_strategy_matrix(key, expected_strategy):
    field = get_field(key)
    assert field is not None
    assert resolved_apply_strategy(field) == expected_strategy


def test_allowed_origins_requires_restart():
    field = get_field("ALLOWED_ORIGINS")
    assert field is not None
    assert field.restart_required is True
    assert resolved_apply_strategy(field) == APPLY_RESTART


def test_env_only_operator_flags_are_admin_visible():
    for key in (
        "CORRELATION_PRECOMPUTE_ENABLED",
        "DETECTION_CONTEXT_SYNC_ENABLED",
        "DETECTION_CONTEXT_NUCLEI_ENABLED",
    ):
        field = get_field(key)
        assert field is not None
        assert field.type == "bool"
        assert resolved_apply_strategy(field) == APPLY_IMMEDIATE


def test_detection_context_llm_flag_requires_restart():
    field = get_field("DETECTION_CONTEXT_LLM_ENABLED")
    assert field is not None
    assert field.type == "bool"
    assert field.restart_required is True
    assert resolved_apply_strategy(field) == APPLY_RESTART


def test_scheduler_reschedule_keys_subset_of_writable():
    assert SCHEDULER_RESCHEDULE_KEYS.issubset(WRITABLE_CONFIG_KEYS)


def test_every_schema_field_has_apply_strategy_in_list():
    for item in list_schema():
        assert item["apply_strategy"] in {
            APPLY_IMMEDIATE,
            APPLY_SCHEDULER_RESCHEDULE,
            APPLY_RESTART,
        }
        assert item["display_label"]


def test_config_schema_endpoint(admin_client):
    resp = admin_client.get("/api/admin/config/schema")
    assert resp.status_code == 200
    data = resp.json()
    keys = {f["key"] for f in data}
    assert "NVD_API_KEY" in keys
    assert "WALLBOARD_TOKEN" in keys
    assert "DISCORD_WEBHOOK_URL" in keys
    assert len(data) == len(WRITABLE_CONFIG_KEYS)


def test_config_get_includes_env_only_operator_flags(admin_client, monkeypatch):
    monkeypatch.setenv("CORRELATION_PRECOMPUTE_ENABLED", "1")
    monkeypatch.setenv("DETECTION_CONTEXT_SYNC_ENABLED", "1")
    monkeypatch.setenv("DETECTION_CONTEXT_LLM_ENABLED", "0")
    monkeypatch.setenv("DETECTION_CONTEXT_NUCLEI_ENABLED", "1")

    resp = admin_client.get("/api/admin/config")

    assert resp.status_code == 200
    ml = resp.json()["ml"]
    assert ml["CORRELATION_PRECOMPUTE_ENABLED"] == "1"
    assert ml["DETECTION_CONTEXT_SYNC_ENABLED"] == "1"
    assert ml["DETECTION_CONTEXT_LLM_ENABLED"] == "0"
    assert ml["DETECTION_CONTEXT_NUCLEI_ENABLED"] == "1"


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
