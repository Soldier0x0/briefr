"""Tests for GET /api/brief — V1.3 morning brief."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brief.service import (
    build_morning_brief,
    _build_epss_movers,
    _detected_at_since_clause,
    _epss_delta,
    _since_hours_cutoff,
    _stack_profile_id,
)
from database import get_db, init_db
from db.pg_adapt import adapt_sql


def _patch_app_lifecycle(monkeypatch) -> None:
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)


async def _seed_brief_db(db_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent_dt = now - timedelta(hours=6)
    recent_text = recent_dt.strftime("%Y-%m-%d %H:%M:%S")
    due_soon = (now + timedelta(days=5)).strftime("%Y-%m-%d")
    published_old = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    modified_recent = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    published_mid = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    modified_mid = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, published, modified,
                affected_products
            ) VALUES (
                'CVE-2024-8001', 'Log4j RCE', 'CRITICAL', 1, 0.92,
                ?, ?, '["apache:log4j"]'
            )
            """,
            (published_old, modified_recent),
        )
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, published, modified,
                affected_products
            ) VALUES (
                'CVE-2024-8002', 'Nginx overflow', 'HIGH', 0, 0.15,
                ?, ?, '["nginx:nginx"]'
            )
            """,
            (published_mid, modified_mid),
        )
        await db.execute(
            """
            INSERT INTO kev_deadlines (
                cve_id, product, short_description, required_action, due_date, date_added
            ) VALUES (
                'CVE-2024-8001', 'Log4j', 'RCE', 'Patch', ?, ?
            )
            """,
            (due_soon, recent_text),
        )
        await db.execute(
            """
            INSERT INTO cve_change_history (
                cve_id, field_name, old_value, new_value, detected_at
            ) VALUES (
                'CVE-2024-8002', 'epss_score', '0.05', '0.15', ?
            )
            """,
            (recent_dt,),
        )
        await db.commit()
    finally:
        await db.close()


def test_stack_profile_id_stable():
    assert _stack_profile_id(["nginx", "log4j"]) == _stack_profile_id(["log4j", "nginx"])
    assert _stack_profile_id([]) is None


def test_brief_endpoint_shape(tmp_path, monkeypatch):
    db_path = tmp_path / "brief.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _patch_app_lifecycle(monkeypatch)

    asyncio.run(init_db())
    asyncio.run(_seed_brief_db(db_path))

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        resp = client.get("/api/brief?stack=log4j,nginx&limit=5")
        assert resp.status_code == 200
        body = resp.json()

    assert "meta" in body
    assert "sections" in body
    assert "action_queue" in body
    assert body["meta"]["since_hours"] == 24
    assert body["meta"]["stack_profile_id"] is not None
    assert "log4j" in body["meta"]["stack_terms"]

    for key in ("epss_movers", "new_kev", "kev_due_soon", "stack_matches", "active_campaigns"):
        assert key in body["sections"]
        assert "items" in body["sections"][key]
        assert "count" in body["sections"][key]

    ids = {item["cve_id"] for item in body["action_queue"]}
    assert "CVE-2024-8001" in ids or "CVE-2024-8002" in ids


def test_brief_kev_due_section(tmp_path, monkeypatch):
    db_path = tmp_path / "brief_kev.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _patch_app_lifecycle(monkeypatch)

    asyncio.run(init_db())
    asyncio.run(_seed_brief_db(db_path))

    async def run() -> dict:
        db = await get_db()
        try:
            return await build_morning_brief(db, stack="log4j", since_hours=24, limit=10)
        finally:
            await db.close()

    result = asyncio.run(run())
    due_items = result["sections"]["kev_due_soon"]["items"]
    assert any(item["cve_id"] == "CVE-2024-8001" for item in due_items)


def test_brief_epss_movers_section(tmp_path, monkeypatch):
    db_path = tmp_path / "brief_epss.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _patch_app_lifecycle(monkeypatch)

    asyncio.run(init_db())
    asyncio.run(_seed_brief_db(db_path))

    async def run() -> dict:
        db = await get_db()
        try:
            return await build_morning_brief(db, stack="nginx", since_hours=24, limit=10)
        finally:
            await db.close()

    result = asyncio.run(run())
    movers = result["sections"]["epss_movers"]["items"]
    assert any(item["cve_id"] == "CVE-2024-8002" for item in movers)
    mover = next(i for i in movers if i["cve_id"] == "CVE-2024-8002")
    assert mover["epss_delta"] == 0.1


def test_brief_active_campaigns_section(tmp_path, monkeypatch):
    db_path = tmp_path / "brief_campaigns.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _patch_app_lifecycle(monkeypatch)

    asyncio.run(init_db())
    asyncio.run(_seed_brief_db(db_path))

    async def seed_campaign():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO correlation_campaigns (
                    campaign_id, primary_pulse_id, label, adversary, confidence,
                    member_count, lifecycle, campaign_version, computed_at
                ) VALUES (
                    'camp_test1', 'pulse-1', 'Log4j wave', 'APT-X', 'high',
                    2, 'active', '2.0.0-phase2', datetime('now')
                )
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_campaign_members (campaign_id, cve_id, role)
                VALUES ('camp_test1', 'CVE-2024-8001', 'member'),
                       ('camp_test1', 'CVE-2024-9999', 'member')
                """
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed_campaign())

    async def run() -> dict:
        db = await get_db()
        try:
            return await build_morning_brief(db, stack="log4j", since_hours=24, limit=10)
        finally:
            await db.close()

    result = asyncio.run(run())
    items = result["sections"]["active_campaigns"]["items"]
    assert len(items) == 1
    assert items[0]["campaign_id"] == "camp_test1"
    assert items[0]["label"] == "Log4j wave"
    assert items[0]["confidence"] == "high"
    assert all("campaign_id" not in item for item in result["action_queue"])


def test_brief_registered_in_openapi():
    from main import app

    routes = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    assert ("GET", "/api/brief") in routes


def test_brief_epss_sql_avoids_real_cast_on_postgres():
    sql = adapt_sql(
        """
        SELECT ch.cve_id FROM cve_change_history ch
        WHERE ch.field_name = 'epss_score'
          AND ch.detected_at >= ?
        ORDER BY ch.detected_at DESC, ch.id DESC
        LIMIT ?
        """,
        backend="postgresql",
    )
    assert "AS REAL" not in sql.upper()
    assert "TO_CHAR" not in sql.upper()


def test_brief_detected_at_clause_uses_bound_cutoff_on_postgres():
    assert _detected_at_since_clause(pg=True) == "ch.detected_at >= ?"
    cutoff = _since_hours_cutoff(24, pg=True)
    assert isinstance(cutoff, datetime)
    assert cutoff.tzinfo is not None


def test_epss_delta_counts_zero_to_positive():
    parsed = _epss_delta("0.0", "0.15")
    assert parsed == (0.0, 0.15, 0.15)

    parsed_empty = _epss_delta("", "0.15")
    assert parsed_empty == (0.0, 0.15, 0.15)

    assert _epss_delta("N/A", "0.15") is None


def test_build_epss_movers_skips_non_numeric_history():
    rows = [
        {
            "cve_id": "CVE-2024-9001",
            "old_value": "0.05",
            "new_value": "0.15",
            "detected_at": "2026-06-23 10:00:00",
            "description": "ok",
            "cvss_score": 7.5,
            "severity": "HIGH",
            "published": "2026-06-01",
            "modified": "2026-06-02",
            "affected_products": "[]",
            "affected_products_source": None,
            "mitre_technique": None,
            "summary": "",
            "is_kev": 0,
            "epss_score": 0.15,
            "has_poc": 0,
            "patch_available": 0,
            "has_ai_context": 0,
            "source_urls": "[]",
            "cwe_ids": "[]",
            "updated_at": "2026-06-02",
            "kev_due_date": None,
        },
        {
            "cve_id": "CVE-2024-9000",
            "old_value": "0.0",
            "new_value": "0.15",
            "detected_at": "2026-06-23 09:00:00",
            "description": "zero baseline",
            "cvss_score": 6.0,
            "severity": "MEDIUM",
            "published": "2026-06-01",
            "modified": "2026-06-02",
            "affected_products": "[]",
            "affected_products_source": None,
            "mitre_technique": None,
            "summary": "",
            "is_kev": 0,
            "epss_score": 0.15,
            "has_poc": 0,
            "patch_available": 0,
            "has_ai_context": 0,
            "source_urls": "[]",
            "cwe_ids": "[]",
            "updated_at": "2026-06-02",
            "kev_due_date": None,
        },
        {
            "cve_id": "CVE-2024-9002",
            "old_value": "N/A",
            "new_value": "0.20",
            "detected_at": "2026-06-23 11:00:00",
            "description": "bad old",
            "cvss_score": 5.0,
            "severity": "MEDIUM",
            "published": "2026-06-01",
            "modified": "2026-06-02",
            "affected_products": "[]",
            "affected_products_source": None,
            "mitre_technique": None,
            "summary": "",
            "is_kev": 0,
            "epss_score": 0.2,
            "has_poc": 0,
            "patch_available": 0,
            "has_ai_context": 0,
            "source_urls": "[]",
            "cwe_ids": "[]",
            "updated_at": "2026-06-02",
            "kev_due_date": None,
        },
    ]
    movers = _build_epss_movers(rows, limit=5)
    assert len(movers) == 2
    by_id = {m["cve_id"]: m for m in movers}
    assert by_id["CVE-2024-9001"]["epss_delta"] == 0.1
    assert by_id["CVE-2024-9000"]["epss_delta"] == 0.15


async def _seed_brief_bad_epss_db(db_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=2)
    published_old = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    modified_recent = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, published, modified,
                affected_products
            ) VALUES (
                'CVE-2024-9010', 'Bad EPSS history row', 'HIGH', 0, 0.2,
                ?, ?, '[]'
            )
            """,
            (published_old, modified_recent),
        )
        await db.execute(
            """
            INSERT INTO cve_change_history (
                cve_id, field_name, old_value, new_value, detected_at
            ) VALUES (
                'CVE-2024-9010', 'epss_score', 'pending', '0.20', ?
            )
            """,
            (recent,),
        )
        await db.commit()
    finally:
        await db.close()


def test_brief_tolerates_non_numeric_epss_history(tmp_path, monkeypatch):
    db_path = tmp_path / "brief_bad_epss.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    _patch_app_lifecycle(monkeypatch)

    asyncio.run(init_db())
    asyncio.run(_seed_brief_bad_epss_db(db_path))

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        resp = client.get("/api/brief?limit=5")
        assert resp.status_code == 200
        body = resp.json()
    assert "action_queue" in body
    assert body["sections"]["epss_movers"]["count"] == 0
