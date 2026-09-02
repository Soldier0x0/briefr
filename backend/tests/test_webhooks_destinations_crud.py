"""Admin CRUD for webhook destinations (PR12b)."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi.testclient import TestClient

import resilient_client
from tests.conftest import run_db_test
from webhooks.destinations import sync_env_destinations_to_db
from webhooks.engine import send_test_message


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "webhooks_crud.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    import routers.admin as _admin_mod

    monkeypatch.setattr(_admin_mod, "trigger_graceful_restart", _noop_async)

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


@pytest.fixture(autouse=True)
def _ssrf_public(monkeypatch):
    async def fake_resolve(_host):
        return ["93.184.216.34"]

    monkeypatch.setattr("webhooks.destinations.resolve_hostname", lambda _host: ["93.184.216.34"])
    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)


def test_create_list_mask_and_delete_destination(admin_client):
    create = admin_client.post(
        "/api/admin/webhooks/destinations",
        json={
            "kind": "discord",
            "id": "discord-ops",
            "label": "Ops alerts",
            "config": {"url": "https://discord.com/api/webhooks/99/secret-token"},
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["destination"]["id"] == "discord-ops"
    assert body["destination"]["source"] == "db"
    assert "[masked]" in body["destination"]["config"]["url"]
    assert "secret-token" not in body["destination"]["config"]["url"]

    listed = admin_client.get("/api/admin/webhooks/destinations")
    assert listed.status_code == 200
    rows = listed.json()["destinations"]
    match = next(row for row in rows if row["id"] == "discord-ops")
    assert "[masked]" in match["config"]["url"]

    deleted = admin_client.delete(
        "/api/admin/webhooks/destinations/discord-ops",
        params={"confirm_text": "delete"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["ok"] is True

    missing = admin_client.get("/api/admin/webhooks/destinations")
    assert all(row["id"] != "discord-ops" for row in missing.json()["destinations"])


def test_create_rejects_non_https_url(admin_client):
    resp = admin_client.post(
        "/api/admin/webhooks/destinations",
        json={
            "kind": "generic",
            "id": "generic-http",
            "config": {"url": "http://hooks.example.com/briefr"},
        },
    )
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"].lower()


def test_patch_config_db_only(admin_client, monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())

    resp = admin_client.patch(
        "/api/admin/webhooks/destinations/discord",
        json={"config": {"url": "https://discord.com/api/webhooks/2/other"}},
    )
    assert resp.status_code == 400
    assert "database-backed" in resp.json()["detail"]


def test_send_test_works_when_disabled(admin_client, monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())

    patch_resp = admin_client.patch(
        "/api/admin/webhooks/destinations/discord",
        json={"enabled": False},
    )
    assert patch_resp.status_code == 200

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)

    result = run_db_test(
        send_test_message("discord", "disabled connectivity check")
    )
    assert result["ok"] is True
    assert calls


def test_per_destination_dedupe_allows_second_destination(admin_client, monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")
    run_db_test(sync_env_destinations_to_db())

    create = admin_client.post(
        "/api/admin/webhooks/destinations",
        json={
            "kind": "discord",
            "id": "discord-backup",
            "config": {"url": "https://discord.com/api/webhooks/2/token"},
        },
    )
    assert create.status_code == 200

    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)

    from webhooks.engine import dispatch_event
    from webhooks.destinations import EVENT_KEV_ALERT

    first = run_db_test(
        dispatch_event(EVENT_KEV_ALERT, "multi", dedupe_key="CVE-2026-1")
    )
    assert first["status"] == "ok"
    assert set(first["sent"]) == {"discord", "discord-backup"}
    assert calls["n"] == 2

    # Simulate discord succeeding but discord-backup failing first time by recording
    # only env discord as sent, then re-dispatch should still hit discord-backup.
    async def record_only_env():
        from database import get_db, record_webhook_destination_sent

        db = await get_db()
        try:
            await record_webhook_destination_sent(
                db, "discord", EVENT_KEV_ALERT, "CVE-2026-2"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(record_only_env())

    second = run_db_test(
        dispatch_event(EVENT_KEV_ALERT, "multi-2", dedupe_key="CVE-2026-2")
    )
    assert "discord-backup" in second["sent"]
    assert "discord" not in second["sent"]


def test_delete_env_discord_succeeds_when_url_only_in_db_config(admin_client, monkeypatch):
    from database import get_db, set_app_setting
    from settings import PROCESS_ENV_KEYS
    from webhooks.destinations import load_env_destinations

    assert "DISCORD_WEBHOOK_URL" not in PROCESS_ENV_KEYS
    url = "https://discord.com/api/webhooks/1/token"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)

    async def seed():
        db = await get_db()
        try:
            await set_app_setting(db, "DISCORD_WEBHOOK_URL", url)
            await set_app_setting(db, "DISCORD_WEBHOOK_ENABLED", "1")
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    run_db_test(sync_env_destinations_to_db())

    deleted = admin_client.delete(
        "/api/admin/webhooks/destinations/discord",
        params={"confirm_text": "delete"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["ok"] is True

    listed = admin_client.get("/api/admin/webhooks/destinations")
    assert listed.status_code == 200
    assert all(row["id"] != "discord" for row in listed.json()["destinations"])
    assert load_env_destinations() == []
    assert not (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()


def test_delete_env_discord_409_when_process_env_set(admin_client, monkeypatch):
    import settings as settings_mod
    from database import get_db, get_webhook_destination_source
    from webhooks.destinations import load_env_destinations

    url = "https://discord.com/api/webhooks/1/token"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)
    monkeypatch.setattr(
        settings_mod,
        "PROCESS_ENV_KEYS",
        frozenset({*settings_mod.PROCESS_ENV_KEYS, "DISCORD_WEBHOOK_URL"}),
    )
    run_db_test(sync_env_destinations_to_db())

    deleted = admin_client.delete(
        "/api/admin/webhooks/destinations/discord",
        params={"confirm_text": "delete"},
    )
    assert deleted.status_code == 409, deleted.text
    detail = deleted.json()["detail"]
    assert "DISCORD_WEBHOOK_URL" in detail
    assert "process environment" in detail
    assert url not in detail
    assert url not in deleted.text

    async def discord_row_source():
        db = await get_db()
        try:
            return await get_webhook_destination_source(db, "discord")
        finally:
            await db.close()

    assert run_db_test(discord_row_source()) is None
    env_ids = {dest.id for dest in load_env_destinations()}
    assert "discord" in env_ids
