"""Correlation phase-4 tail: feed boost for CVEs linked to pinned campaign peers."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from database import init_db


def _force_sqlite(tmp_path, monkeypatch):
    from settings import settings

    db_path = tmp_path / "feed_watchlist_sort.db"
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


async def _seed_feed_campaign_graph(db) -> None:
    published = "2026-01-15T12:00:00Z"
    for cve_id, desc in (
        ("CVE-2026-PEER-001", "Pinned campaign anchor"),
        ("CVE-2026-PEER-002", "Peer in same campaign"),
        ("CVE-2026-PEER-003", "Unrelated CVE"),
    ):
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, published, modified, is_kev, has_poc
            ) VALUES (?, ?, 'HIGH', ?, ?, 0, 0)
            """,
            (cve_id, desc, published, published),
        )

    await db.execute(
        """
        INSERT INTO watchlist (cve_id, state, snooze_until)
        VALUES ('CVE-2026-PEER-001', 'pin', NULL)
        """
    )
    await db.execute(
        """
        INSERT INTO correlation_campaigns (
            campaign_id, primary_pulse_id, label, confidence,
            member_count, lifecycle
        ) VALUES ('camp_peer', 'pulse-peer', 'Peer campaign', 'medium', 2, 'active')
        """
    )
    for cve_id in ("CVE-2026-PEER-001", "CVE-2026-PEER-002"):
        await db.execute(
            """
            INSERT INTO correlation_campaign_members (campaign_id, cve_id, role)
            VALUES ('camp_peer', ?, 'member')
            """,
            (cve_id,),
        )


def test_feed_boosts_campaign_peer_of_pinned_cve(tmp_path, monkeypatch):
    db_path = _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await _seed_feed_campaign_graph(db)
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves", params={"limit": 10})

    assert res.status_code == 200
    rows = res.json()["data"]
    ids = [row["cve_id"] for row in rows]
    assert ids.index("CVE-2026-PEER-001") < ids.index("CVE-2026-PEER-002")
    assert ids.index("CVE-2026-PEER-002") < ids.index("CVE-2026-PEER-003")


def test_feed_skips_boost_for_low_confidence_campaign(tmp_path, monkeypatch):
    db_path = _force_sqlite(tmp_path, monkeypatch)
    asyncio.run(init_db())

    async def seed() -> None:
        db = await aiosqlite.connect(db_path)
        try:
            await _seed_feed_campaign_graph(db)
            await db.execute(
                """
                UPDATE cves SET epss_score = 0.9 WHERE cve_id = 'CVE-2026-PEER-003'
                """
            )
            await db.execute(
                """
                UPDATE correlation_campaigns
                SET confidence = 'low', lifecycle = 'stale'
                WHERE campaign_id = 'camp_peer'
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())

    from main import app

    with TestClient(app) as client:
        res = client.get("/api/cves", params={"limit": 10})

    assert res.status_code == 200
    rows = res.json()["data"]
    ids = [row["cve_id"] for row in rows]
    assert ids.index("CVE-2026-PEER-001") < ids.index("CVE-2026-PEER-003")
    assert ids.index("CVE-2026-PEER-003") < ids.index("CVE-2026-PEER-002")
