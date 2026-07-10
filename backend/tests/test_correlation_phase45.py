"""Phase 4–5: GET /api/correlation/clusters and GET /api/admin/correlation/status."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from correlation.campaigns import (
    CORRELATION_LAST_RUN_KEY,
    build_campaigns_from_pulses,
)
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs, set_sync_state_value


def _force_sqlite(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "corr_phase45.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)
    monkeypatch.setattr(settings, "briefr_require_postgres", False)

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)
    return db_path


async def _seed_cve(db, cve_id: str, products: str = "log4j", *, description: str | None = None) -> None:
    desc = description or f"{products} cluster test CVE"
    await db.execute(
        """
        INSERT INTO cves (
            cve_id, description, severity, published, modified,
            affected_products, is_kev, has_poc
        ) VALUES (?, ?, 'HIGH', datetime('now'), datetime('now'), ?, 0, 0)
        """,
        (cve_id, desc, f'["apache:{products}"]'),
    )


async def _seed_campaign_graph(db) -> None:
    await _seed_cve(db, "CVE-2026-CLU-001", "log4j", description="Log4j RCE")
    await _seed_cve(db, "CVE-2026-CLU-002", "log4j", description="Log4j deserialization")
    await _seed_cve(db, "CVE-2026-CLU-003", "nginx", description="Nginx overflow")
    await _seed_cve(db, "CVE-2026-CLU-004", "nginx", description="Nginx proxy issue")

    pulses_a = [
        {
            "pulse_id": "pulse-cluster-a",
            "pulse_name": "Log4j campaign",
            "author": "analyst",
            "created_date": "2026-01-01",
            "adversary": "APT-TEST",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2026-CLU-001", pulses_a)
    await replace_otx_cve_pulses(db, "CVE-2026-CLU-002", pulses_a)

    pulses_b = [
        {
            "pulse_id": "pulse-cluster-b",
            "pulse_name": "Nginx side campaign",
            "author": "analyst",
            "created_date": "2026-01-02",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 0,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2026-CLU-003", pulses_b)
    await replace_otx_cve_pulses(db, "CVE-2026-CLU-004", pulses_b)

    await replace_otx_pulse_iocs(
        db,
        "pulse-cluster-a",
        [{"ioc_type": "domain", "ioc_value": "evil.example", "description": ""}],
    )


async def _build_campaigns() -> None:
    from database import get_db

    db = await get_db()
    try:
        await build_campaigns_from_pulses(db)
        await db.commit()
    finally:
        await db.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        from database import get_db

        db = await get_db()
        try:
            await _seed_campaign_graph(db)
            await db.execute(
                """
                INSERT INTO watchlist (cve_id, state, snooze_until)
                VALUES ('CVE-2026-CLU-002', 'pin', NULL)
                """
            )
            await set_sync_state_value(db, CORRELATION_LAST_RUN_KEY, "2026-07-08T12:00:00Z")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())
    asyncio.run(_build_campaigns())

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        from database import get_db

        db = await get_db()
        try:
            await _seed_campaign_graph(db)
            await set_sync_state_value(db, CORRELATION_LAST_RUN_KEY, "2026-07-08T12:00:00Z")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())
    asyncio.run(_build_campaigns())

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.cookies.set("briefr_at", auth_token())
        yield test_client


def test_correlation_clusters_stack_filter_and_watchlist_boost(client):
    res = client.get("/api/correlation/clusters", params={"stack": "log4j", "limit": 10})
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["stack_terms"] == ["log4j"]
    assert body["meta"]["count"] >= 1

    clusters = body["clusters"]
    by_label = {cluster["label"]: cluster for cluster in clusters}
    assert "Log4j campaign" in by_label
    log4j = by_label["Log4j campaign"]
    assert log4j["stack_member_count"] >= 2
    assert log4j["watchlisted_member_count"] >= 1
    assert "CVE-2026-CLU-002" in log4j["watchlisted_members"]
    assert clusters[0]["label"] == "Log4j campaign"


def test_correlation_clusters_excludes_stale_by_default(client):
    res = client.get("/api/correlation/clusters", params={"limit": 50})
    assert res.status_code == 200
    for cluster in res.json()["clusters"]:
        assert cluster["lifecycle"] != "stale"


def test_correlation_clusters_registered_in_openapi():
    from main import app

    routes = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    assert ("GET", "/api/correlation/clusters") in routes


def test_correlation_clusters_cve_id_filter(client):
    res = client.get(
        "/api/correlation/clusters",
        params={"cve_id": "CVE-2026-CLU-002", "limit": 10},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["cve_id"] == "CVE-2026-CLU-002"
    labels = {cluster["label"] for cluster in body["clusters"]}
    assert "Log4j campaign" in labels
    assert "Nginx campaign" not in labels


def test_admin_correlation_status(admin_client):
    res = admin_client.get("/api/admin/correlation/status")
    assert res.status_code == 200
    body = res.json()
    assert body["last_run"]
    assert body["build_watermark"]
    assert body["campaigns"]["total"] >= 2
    assert body["features"]["feed_campaign_sort_boost"] is True
    assert body["coverage"]["cves_total"] == 4
    assert body["coverage"]["otx_pulses_linked"] == 2
    assert body["coverage"]["otx_pulses_with_iocs"] == 1
    assert body["backlog"]["ioc_sync_pending_pulses"] == 1
    assert "campaign_coverage_pct" in body["coverage"]
