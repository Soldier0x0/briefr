"""Operator settings in DB — precedence and admin persistence."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database
from database import get_app_setting, get_db, init_db, set_app_setting
from operator_settings import hydrate_operator_settings_from_db, persist_operator_setting
from settings import PROCESS_ENV_KEYS


def _sqlite_db(tmp_path, monkeypatch) -> str:
    from settings import settings

    db_path = str(tmp_path / "app_settings.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)
    monkeypatch.setattr(settings, "briefr_require_postgres", False)

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)
    return db_path


def test_admin_set_config_persists_to_app_settings(tmp_path, monkeypatch, auth_token):
    db_path = _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        resp = client.post(
            "/api/admin/config",
            json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "4"},
        )

    assert resp.status_code == 200

    async def read():
        db = await get_db()
        try:
            return await get_app_setting(db, "NVD_SYNC_INTERVAL_HOURS")
        finally:
            await db.close()

    assert run_db_test(read()) == "4"


def test_hydrate_applies_db_over_dotenv(tmp_path, monkeypatch):
    db_path = _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())

    monkeypatch.setenv("EPSS_SYNC_INTERVAL_HOURS", "6")

    async def seed():
        db = await get_db()
        try:
            await set_app_setting(db, "EPSS_SYNC_INTERVAL_HOURS", "12")
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    applied = run_db_test(hydrate_operator_settings_from_db())
    assert applied >= 1
    assert os.environ["EPSS_SYNC_INTERVAL_HOURS"] == "12"


def test_hydrate_skips_process_env_keys(tmp_path, monkeypatch):
    db_path = _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())

    key = "KEV_SYNC_INTERVAL_MINUTES"
    monkeypatch.setenv(key, "99")
    monkeypatch.setattr(
        "operator_settings.PROCESS_ENV_KEYS",
        frozenset({*PROCESS_ENV_KEYS, key}),
    )

    async def seed():
        db = await get_db()
        try:
            await set_app_setting(db, key, "15")
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    run_db_test(hydrate_operator_settings_from_db())
    assert os.environ[key] == "99"


def test_persist_operator_setting_round_trip(tmp_path, monkeypatch):
    _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())

    run_db_test(persist_operator_setting("BACKUP_INTERVAL_HOURS", "8"))

    async def read():
        db = await get_db()
        try:
            return await get_app_setting(db, "BACKUP_INTERVAL_HOURS")
        finally:
            await db.close()

    assert run_db_test(read()) == "8"


def test_persist_secret_encrypts_when_settings_key_set(tmp_path, monkeypatch):
    _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())
    monkeypatch.setenv("BRIEFR_SETTINGS_KEY", "unit-test-settings-key")

    run_db_test(persist_operator_setting("NVD_API_KEY", "plain-nvd-secret"))

    async def read():
        db = await get_db()
        try:
            return await get_app_setting(db, "NVD_API_KEY")
        finally:
            await db.close()

    stored = run_db_test(read())
    assert stored is not None
    assert stored.startswith("enc:v1:")
    assert "plain-nvd-secret" not in stored


def test_persist_secret_skips_db_without_settings_key(tmp_path, monkeypatch):
    _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())
    monkeypatch.delenv("BRIEFR_SETTINGS_KEY", raising=False)

    run_db_test(persist_operator_setting("NVD_API_KEY", "only-in-env"))

    async def read():
        db = await get_db()
        try:
            return await get_app_setting(db, "NVD_API_KEY")
        finally:
            await db.close()

    assert run_db_test(read()) is None


def test_hydrate_decrypts_secret_rows(tmp_path, monkeypatch):
    _sqlite_db(tmp_path, monkeypatch)
    run_db_test(init_db())
    monkeypatch.setenv("BRIEFR_SETTINGS_KEY", "unit-test-settings-key")
    # Ensure hydrate is allowed to apply this key (not in process-env snapshot).
    monkeypatch.setattr(
        "operator_settings.PROCESS_ENV_KEYS",
        frozenset(k for k in PROCESS_ENV_KEYS if k != "NVD_API_KEY"),
    )

    run_db_test(persist_operator_setting("NVD_API_KEY", "hydrated-secret"))
    monkeypatch.delenv("NVD_API_KEY", raising=False)

    applied = run_db_test(hydrate_operator_settings_from_db())
    assert applied >= 1
    assert os.environ["NVD_API_KEY"] == "hydrated-secret"
