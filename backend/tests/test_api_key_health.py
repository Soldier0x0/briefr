"""API key health ping monitoring."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_run_api_key_health_checks_skips_placeholders(monkeypatch, tmp_path):
    from database import get_db, init_db
    from monitoring import api_key_health as mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health.db"))
    asyncio.run(init_db())

    monkeypatch.setenv("GROQ_API_KEY", "your_key_here")
    monkeypatch.setenv("NVD_API_KEY", "")

    async def fake_ping(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        return response

    monkeypatch.setattr(mod, "resilient_request", fake_ping)

    async def run() -> dict:
        db = await get_db()
        try:
            return await mod.run_api_key_health_checks(db)
        finally:
            await db.close()

    stats = asyncio.run(run())
    assert stats["checked"] == 0


def test_run_api_key_health_checks_persists_result(monkeypatch, tmp_path):
    from database import get_db, get_sync_state_value, init_db
    from monitoring import api_key_health as mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health2.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testkey1234567890abcd")

    async def fake_ping(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        return response

    monkeypatch.setattr(mod, "resilient_request", fake_ping)

    async def run() -> tuple[dict, str | None]:
        db = await get_db()
        try:
            stats = await mod.run_api_key_health_checks(db)
            raw = await get_sync_state_value(db, "api_key_health:groq")
            return stats, raw
        finally:
            await db.close()

    stats, raw = asyncio.run(run())
    assert stats["checked"] == 1
    assert stats["healthy"] == 1
    payload = json.loads(raw)
    assert payload["healthy"] is True
    assert payload["checked_at"]


def test_build_api_key_health_payload_suffix(monkeypatch, tmp_path):
    from database import get_db, init_db, set_sync_state_value
    from monitoring.api_key_health import build_api_key_health_payload

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health3.db"))
    asyncio.run(init_db())
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey1234567890")

    async def run() -> dict:
        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                "api_key_health:gemini",
                json.dumps(
                    {
                        "provider": "gemini",
                        "healthy": False,
                        "checked_at": "2026-07-10T12:00:00+00:00",
                        "latency_ms": 120,
                        "status_code": 403,
                        "error": "HTTP 403",
                    }
                ),
            )
            await db.commit()
            return await build_api_key_health_payload(db)
        finally:
            await db.close()

    payload = asyncio.run(run())
    gemini = next(row for row in payload["providers"] if row["provider"] == "gemini")
    assert gemini["configured"] is True
    assert gemini["key_suffix"].startswith("AIza")
    assert gemini["healthy"] is False
    assert gemini["error"] == "HTTP 403"
