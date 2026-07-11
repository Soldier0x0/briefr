"""Tests for /api/admin/config endpoints."""

import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "config.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("NVD_API_KEY", "supersecretkey1234")
    monkeypatch.setenv("VIRUSTOTAL_API_KEY", "")

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    # apply-all/restart schedule trigger_graceful_restart as a background task,
    # which TestClient runs synchronously within the request — a real
    # os.kill(SIGTERM) here would kill the test process itself. Neutralize it.
    import routers.admin as _admin_mod
    monkeypatch.setattr(_admin_mod, "trigger_graceful_restart", _noop_async)

    # Disable rate limiting so tests don't hit 429
    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    # Context-manager form runs FastAPI lifespan (schema init + pool
    # open/close) scoped to this test's event loop — required on Postgres,
    # where get_connection() needs init_pool() to have already run.
    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_config_api_keys_are_masked(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data["api_keys"]

    # Each key must be masked or 'not configured'
    masked_pattern = re.compile(r"^.{4}….{4}$|^not configured$|^\*\*\*$")
    for key, val in api_keys.items():
        assert val == "not configured" or masked_pattern.match(val), (
            f"Key {key!r} not properly masked: {val!r}"
        )


def test_config_no_full_key_values(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data["api_keys"]

    # The NVD_API_KEY was set to "supersecretkey1234" — masked first4…last4
    nvd_val = api_keys.get("NVD_API_KEY", "")
    assert "supersecretkey" not in nvd_val
    assert nvd_val == "supe…1234"


def test_admin_key_not_in_response(admin_client):
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()

    def _flatten(d, path=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield from _flatten(v, f"{path}.{k}" if path else k)
        elif isinstance(d, list):
            for item in d:
                yield from _flatten(item, path)
        else:
            yield path, d

    for path, val in _flatten(data):
        assert "BRIEFR_ADMIN_API_KEY" not in path, f"Admin key path found: {path}"


def test_config_set_allowlisted_key(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config",
            json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "2"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["key"] == "NVD_SYNC_INTERVAL_HOURS"
    assert data["apply_strategy"] == "scheduler_reschedule"


def test_config_set_allowed_origins_warns_restart(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config",
            json={"key": "ALLOWED_ORIGINS", "value": "http://localhost:5173"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["apply_strategy"] == "restart"
    assert data["warning_restart_required"] is True


def test_config_set_reschedules_scheduler_job(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"), patch(
        "scheduler.reschedule_jobs_for_keys",
        return_value={
            "rescheduled": ["nvd_incremental_sync"],
            "skipped": [],
            "scheduler_running": True,
        },
    ) as mock_reschedule:
        resp = admin_client.post(
            "/api/admin/config",
            json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "2"},
        )
    assert resp.status_code == 200
    data = resp.json()
    mock_reschedule.assert_called_once_with(["NVD_SYNC_INTERVAL_HOURS"])
    assert data["rescheduled_jobs"] == ["nvd_incremental_sync"]


def test_config_set_non_integer_for_integer_key(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "NVD_SYNC_INTERVAL_HOURS", "value": "not_a_number"},
    )
    assert resp.status_code == 400


def test_config_set_non_allowlisted_key(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "SECRET_KEY", "value": "anything"},
    )
    assert resp.status_code == 400


def test_config_set_admin_key_rejected(admin_client):
    resp = admin_client.post(
        "/api/admin/config",
        json={"key": "BRIEFR_ADMIN_API_KEY", "value": "hacked"},
    )
    assert resp.status_code == 400


def test_apply_all_non_allowlisted_key_returns_400(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config/apply-all",
            json=[{"key": "SECRET_UNALLOWED_KEY", "value": "anything"}],
        )
    assert resp.status_code == 400


def test_apply_all_writes_allowed_key(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config/apply-all",
            json=[{"key": "NVD_SYNC_INTERVAL_HOURS", "value": "3"}],
        )
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert data["ok"] is True
    assert "NVD_SYNC_INTERVAL_HOURS" in data["changed_keys"]
    assert data["restart_required"] is False


def test_apply_all_restart_for_allowed_origins(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config/apply-all",
            json=[{"key": "ALLOWED_ORIGINS", "value": "http://example.com"}],
        )
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert data["restart_required"] is True
    assert "ALLOWED_ORIGINS" in data["changed_keys"]


def test_apply_all_empty_body_returns_no_changes(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    resp = admin_client.post("/api/admin/config/apply-all", json=[])
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["changed_keys"] == []


def test_config_set_secret_masks_response_and_audit(admin_client, tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("")
    import routers.admin as admin_mod
    monkeypatch.setattr(admin_mod, "_DOTENV_PATH", dotenv_path)

    async def _noop_persist(*args, **kwargs):
        return None

    monkeypatch.setattr("operator_settings.persist_operator_setting", _noop_persist)

    secret = "supersecretgroqkey9999"
    with patch("dotenv.set_key"):
        resp = admin_client.post(
            "/api/admin/config",
            json={"key": "GROQ_API_KEY", "value": secret},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert secret not in data["masked_value"]
    assert data["masked_value"] == "supe…9999"

    audit_resp = admin_client.get("/api/admin/audit-log?limit=5&action_prefix=config.set.")
    assert audit_resp.status_code == 200
    rows = audit_resp.json().get("rows", [])
    config_rows = [r for r in rows if r.get("action") == "config.set.GROQ_API_KEY"]
    assert config_rows
    assert secret not in (config_rows[0].get("target") or "")


def test_api_keys_never_returned_full_value(admin_client):
    """No API key should be returned in cleartext — only masked or not configured."""
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    api_keys = data.get("api_keys", {})

    for key, val in api_keys.items():
        # Must be masked format or "not configured"
        assert val in ("not configured", "***") or (
            len(val) >= 9 and "…" in val and val[:4] != val[-4:]
        ), (
            f"Key {key!r} looks like it may be unmasked: {val!r}"
        )


def test_audit_log_masks_legacy_plaintext_targets(admin_client):
    """Legacy rows stored before write-path redaction must be masked on read."""
    import database as db_mod
    from tests.conftest import run_db_test

    secret = "gsk_legacyPlaintextKey9999"

    async def _seed():
        db = await db_mod.get_db()
        try:
            await db.execute(
                """
                INSERT INTO audit_log (actor, action, target)
                VALUES ('admin', 'config.set.GROQ_API_KEY', ?)
                """,
                (secret,),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())

    resp = admin_client.get("/api/admin/audit-log?limit=5&action_prefix=config.set.")
    assert resp.status_code == 200
    rows = resp.json().get("rows", [])
    groq_rows = [r for r in rows if r.get("action") == "config.set.GROQ_API_KEY"]
    assert groq_rows
    assert secret not in (groq_rows[0].get("target") or "")
    assert "…" in groq_rows[0]["target"]
