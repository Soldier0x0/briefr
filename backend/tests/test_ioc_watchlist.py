"""Tests for IOC watchlist + retro-match (V1.5 Theme 4b)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import get_db, init_db
from feeds.threatfox import parse_threatfox_ioc
from ioc.retro_match import find_retro_matches
from tests.conftest import run_db_test, seed_pytest_auth_user_if_missing


@pytest.fixture
def ioc_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "ioc_watchlist.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role)
                VALUES (1, 'pytest-admin', 'hash', 'admin')
                """
            )
            await db.execute(
                """
                INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value, label)
                VALUES (1, 'domain', 'evil.example', 'test label')
                """
            )
            await db.execute(
                """
                INSERT INTO otx_pulse_iocs (pulse_id, ioc_type, ioc_value, description)
                VALUES ('pulse-1', 'DOMAIN', 'evil.example', 'OTX hit')
                """
            )
            await db.execute(
                """
                INSERT INTO threatfox_iocs (
                    ioc_id, ioc_type, ioc_value, raw_ioc, malware, threat_type,
                    confidence_level, first_seen
                ) VALUES ('tf-1', 'domain', 'evil.example', 'evil.example', 'vidar', 'botnet_cc', 100, '2024-01-01')
                """
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


@pytest.mark.no_auth
def test_ioc_watchlist_requires_auth(tmp_path, monkeypatch):
    db_path = tmp_path / "ioc_auth.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/ioc/watchlist")
    assert resp.status_code == 401


def test_list_and_add_watchlist(ioc_client):
    resp = ioc_client.get("/api/ioc/watchlist")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1

    add = ioc_client.post(
        "/api/ioc/watchlist",
        json={"value": "1.2.3.4", "type": "ip", "label": "scanner"},
    )
    assert add.status_code == 200
    assert add.json()["item"]["ioc_value"] == "1.2.3.4"

    listed = ioc_client.get("/api/ioc/watchlist")
    assert len(listed.json()["items"]) == 2


def test_delete_watchlist_entry(ioc_client):
    entry_id = ioc_client.get("/api/ioc/watchlist").json()["items"][0]["id"]
    resp = ioc_client.delete(f"/api/ioc/watchlist/{entry_id}")
    assert resp.status_code == 200
    assert ioc_client.get("/api/ioc/watchlist").json()["items"] == []


def test_parse_threatfox_ioc_url_extracts_domain():
    row = parse_threatfox_ioc(
        {
            "id": "99",
            "ioc": "http://116.202.5.101/malware",
            "ioc_type": "url",
            "malware_printable": "Vidar",
            "confidence_level": 100,
            "first_seen": "2024-01-01",
        }
    )
    assert row is not None
    assert row["ioc_type"] == "domain"
    assert row["ioc_value"] == "116.202.5.101"


def test_retro_match_local_join(tmp_path, monkeypatch):
    db_path = tmp_path / "retro.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    run_db_test(init_db())
    seed_pytest_auth_user_if_missing()

    async def seed() -> None:
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value) VALUES (1, 'domain', 'evil.example')"
            )
            await db.execute(
                "INSERT INTO otx_pulse_iocs (pulse_id, ioc_type, ioc_value) VALUES ('p1', 'DOMAIN', 'evil.example')"
            )
            await db.execute(
                """
                INSERT INTO correlation_campaigns (
                    campaign_id, primary_pulse_id, label, confidence,
                    member_count, lifecycle
                ) VALUES ('camp_p1', 'p1', 'Evil pulse cluster', 'high', 4, 'active')
                """
            )
            await db.execute(
                """
                INSERT INTO threatfox_iocs (
                    ioc_id, ioc_type, ioc_value, raw_ioc, malware, threat_type,
                    confidence_level, first_seen
                ) VALUES (
                    't1', 'domain', 'evil.example', 'evil.example',
                    'vidar', 'botnet_cc', 90, '2024-06-01'
                )
                """
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())
    async def check():
        db = await get_db()
        try:
            return await find_retro_matches(db)
        finally:
            await db.close()

    matches = run_db_test(check())
    sources = {m["source"] for m in matches}
    assert sources == {"otx", "threatfox"}

    otx = next(m for m in matches if m["source"] == "otx")
    assert otx["campaign_id"] == "camp_p1"
    assert otx["campaign_label"] == "Evil pulse cluster"
    assert otx["campaign_lifecycle"] == "active"
    assert otx["campaign_confidence"] == "high"
    assert otx["campaign_member_count"] == 4

    tf = next(m for m in matches if m["source"] == "threatfox")
    assert tf["threatfox_confidence"] == 90
    assert tf["threatfox_malware"] == "vidar"
    assert tf["threatfox_threat_type"] == "botnet_cc"
    assert tf["threatfox_first_seen"] == "2024-06-01"


def test_ioc_watchlist_hit_webhook_format(tmp_path, monkeypatch):
    from webhooks.alerts import _format_ioc_watchlist_hit, process_ioc_watchlist_hit_webhooks

    otx_msg = _format_ioc_watchlist_hit(
        {
            "ioc_value": "evil.example",
            "ioc_type": "domain",
            "source": "otx",
            "label": "c2",
            "detail": "OTX pulse hit",
            "campaign_id": "camp_p1",
            "campaign_label": "Evil pulse cluster",
            "campaign_lifecycle": "active",
            "campaign_confidence": "high",
            "campaign_member_count": 4,
        }
    )
    assert "IOC watchlist hit (OTX)" in otx_msg
    assert "Campaign: Evil pulse cluster" in otx_msg
    assert "4 linked CVEs" in otx_msg

    tf_msg = _format_ioc_watchlist_hit(
        {
            "ioc_value": "evil.example",
            "ioc_type": "domain",
            "source": "threatfox",
            "detail": "vidar",
            "threatfox_confidence": 90,
            "threatfox_malware": "vidar",
            "threatfox_threat_type": "botnet_cc",
            "threatfox_first_seen": "2024-06-01",
        }
    )
    assert "ThreatFox confidence: 90/100" in tf_msg
    assert "Threat type: botnet_cc" in tf_msg
    assert "First seen: 2024-06-01" in tf_msg

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(204)

    import httpx
    import resilient_client
    from webhooks.destinations import sync_env_destinations_to_db

    db_path = tmp_path / "ioc_webhook.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    run_db_test(init_db())
    run_db_test(sync_env_destinations_to_db())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(resilient_client, "_client", client)
    monkeypatch.setattr("webhooks.ssrf._webhook_client", client)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/token")

    async def fake_resolve(_host):
        return ["93.184.216.34"]

    monkeypatch.setattr("webhooks.ssrf.async_resolve_hostname", fake_resolve)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(resilient_client.asyncio, "sleep", no_sleep)
    resilient_client.reset_feed_health()
    run_db_test(sync_env_destinations_to_db())

    sent = run_db_test(
        process_ioc_watchlist_hit_webhooks(
            [
                {
                    "user_id": 1,
                    "ioc_value": "evil.example",
                    "source": "otx",
                    "ioc_type": "domain",
                    "campaign_id": "camp_p1",
                    "campaign_label": "Evil pulse cluster",
                    "campaign_lifecycle": "active",
                    "campaign_confidence": "high",
                    "campaign_member_count": 2,
                }
            ]
        )
    )
    assert sent == 1
    assert len(calls) == 1
    assert "Campaign: Evil pulse cluster" in calls[0].content.decode()


def test_vulncheck_kev_tier_score():
    from scoring.risk import _kev_score_v11b

    assert _kev_score_v11b({"is_kev": 1, "kev_date_added": None}) == 0.84
    assert _kev_score_v11b({"is_kev": 0, "is_vulncheck_exploited": 1}) == 0.72
    assert _kev_score_v11b({"is_kev": 0, "is_vulncheck_exploited": 0}) == 0.0
