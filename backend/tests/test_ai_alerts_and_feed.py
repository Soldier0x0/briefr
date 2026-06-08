"""Tests for AI/ML alerts stats and combined case-studies feed."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
import pytest

from database import init_db


async def _seed_ai_cve(db_path: Path) -> None:
    await init_db()
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, published, affected_products, has_ai_context
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "CVE-2024-TFLOW",
                "Remote code execution in TensorFlow serving.",
                "CRITICAL",
                "2024-01-01",
                json.dumps(["google:tensorflow"]),
                1,
            ),
        )
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, published, affected_products, has_ai_context
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "CVE-2024-NGINX",
                "Buffer overflow in nginx.",
                "HIGH",
                "2024-01-02",
                json.dumps(["nginx:nginx"]),
                0,
            ),
        )
        await db.commit()
    finally:
        await db.close()


def test_stats_ai_ml_alerts_with_frameworks(tmp_path, monkeypatch):
    db_path = tmp_path / "ai.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    asyncio.run(_seed_ai_cve(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/stats?frameworks=tensorflow")
        assert res.status_code == 200
        body = res.json()
        assert body["ai_ml_alerts"] == 1

        list_res = client.get("/api/cves?frameworks=tensorflow&ai_context_only=true")
        assert list_res.status_code == 200
        data = list_res.json()["data"]
        assert len(data) == 1
        assert data[0]["cve_id"] == "CVE-2024-TFLOW"
        assert data[0]["has_ai_context"] is True


def test_case_studies_feed_endpoint(tmp_path, monkeypatch):
    db_path = tmp_path / "feed.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def seed() -> None:
        await init_db()

    asyncio.run(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        res = client.get("/api/case-studies/feed?atlas_limit=5")
        assert res.status_code == 200
        body = res.json()
        assert "data" in body
        assert "errors" in body
        assert isinstance(body["data"], list)
