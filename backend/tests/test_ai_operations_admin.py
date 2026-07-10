"""Admin AI operations APIs (AI-2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from ai.operations_admin import build_providers_payload
from database import (
    ai_operations_usage_since,
    get_db,
    init_db,
    insert_ai_operation,
    list_ai_operations_page,
)
from tests.conftest import run_db_test


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "ai_ops_admin2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    import rate_limit as _rl
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_providers_payload_lists_four_providers():
    payload = build_providers_payload()
    names = [p["provider"] for p in payload["providers"]]
    assert names == ["groq", "gemini", "cerebras", "openrouter"]
    assert all("configured" in p for p in payload["providers"])


def test_usage_aggregates_and_activity_pagination(tmp_path, monkeypatch):
    db_path = tmp_path / "ai_ops_usage.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation(
                db,
                operation_id="u1",
                request_id=None,
                started_at="2099-01-01T00:00:00Z",
                latency_ms=10,
                feature="pdf_summary",
                task_class="pdf_summary",
                provider="groq",
                model="m1",
                success=True,
            )
            await insert_ai_operation(
                db,
                operation_id="u2",
                request_id=None,
                started_at="2099-01-01T00:01:00Z",
                latency_ms=20,
                feature="pdf_summary",
                task_class="pdf_summary",
                provider="gemini",
                model="m2",
                success=False,
                error_class="empty",
                fallback_from_provider="groq",
                fallback_from_model="m1",
            )
            await db.commit()
            usage = await ai_operations_usage_since(db, hours=24 * 365)
            assert usage["total"] == 2
            assert usage["failures"] == 1
            rows, total = await list_ai_operations_page(db, limit=1, offset=0)
            assert total == 2
            assert len(rows) == 1
            rows2, _ = await list_ai_operations_page(
                db, limit=10, offset=0, provider="gemini"
            )
            assert len(rows2) == 1
            assert rows2[0]["provider"] == "gemini"
        finally:
            await db.close()

    run_db_test(_run())


def test_admin_ai_operations_endpoints(admin_client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    overview = admin_client.get("/api/admin/ai/operations/overview")
    assert overview.status_code == 200
    ov = overview.json()
    assert "usage" in ov
    assert ov["usage"]["24h"]["tokens_recorded"] is False
    assert "features" in ov

    providers = admin_client.get("/api/admin/ai/operations/providers")
    assert providers.status_code == 200
    assert len(providers.json()["providers"]) == 4

    activity = admin_client.get("/api/admin/ai/operations/activity?limit=10&offset=0")
    assert activity.status_code == 200
    assert "rows" in activity.json()
    assert "total" in activity.json()
