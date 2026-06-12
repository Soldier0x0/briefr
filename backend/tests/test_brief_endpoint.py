"""Tests for GET /api/brief — V1.3 morning brief."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from brief.service import build_morning_brief, _stack_profile_id
from database import get_db, init_db


def _patch_app_lifecycle(monkeypatch) -> None:
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)


async def _seed_brief_db(db_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    due_soon = (now + timedelta(days=5)).strftime("%Y-%m-%d")

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, published, modified,
                affected_products
            ) VALUES (
                'CVE-2024-8001', 'Log4j RCE', 'CRITICAL', 1, 0.92,
                datetime('now', '-2 days'), datetime('now', '-1 hour'), '["apache:log4j"]'
            )
            """
        )
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, published, modified,
                affected_products
            ) VALUES (
                'CVE-2024-8002', 'Nginx overflow', 'HIGH', 0, 0.15,
                datetime('now', '-12 hours'), datetime('now', '-6 hours'), '["nginx:nginx"]'
            )
            """
        )
        await db.execute(
            """
            INSERT INTO kev_deadlines (
                cve_id, product, short_description, required_action, due_date, date_added
            ) VALUES (
                'CVE-2024-8001', 'Log4j', 'RCE', 'Patch', ?, ?
            )
            """,
            (due_soon, recent),
        )
        await db.execute(
            """
            INSERT INTO cve_change_history (
                cve_id, field_name, old_value, new_value, detected_at
            ) VALUES (
                'CVE-2024-8002', 'epss_score', '0.05', '0.15', ?
            )
            """,
            (recent,),
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

    for key in ("epss_movers", "new_kev", "kev_due_soon", "stack_matches"):
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


def test_brief_registered_in_openapi():
    from main import app

    routes = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }
    assert ("GET", "/api/brief") in routes
