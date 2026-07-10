"""AI operations persistence and model catalog (AI-1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import db.ai_operations as ai_ops_mod
from ai.model_catalog import models_catalog_payload, task_chain
from db.config import is_postgres
from db.timeutil import utcnow_str
from database import count_ai_operations, get_db, init_db, insert_ai_operation, list_ai_operations
from tests.conftest import run_db_test


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "ai_ops_admin.db"
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


def test_ai_operations_sql_uses_native_placeholders():
    if is_postgres():
        assert "$1" in ai_ops_mod._INSERT_PG
        assert "$19" in ai_ops_mod._INSERT_PG
    else:
        assert "?" in ai_ops_mod._INSERT_SQLITE


def test_insert_and_list_ai_operations(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "ai_ops.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await count_ai_operations(db) == 0
            await insert_ai_operation(
                db,
                operation_id="op-1",
                request_id="req-abc",
                started_at="2026-07-10T12:00:00Z",
                latency_ms=42,
                feature="pdf_summary",
                task_class="pdf_summary",
                provider="groq",
                model="openai/gpt-oss-120b",
                success=True,
                retry_index=0,
                context_type="cve",
                context_id="CVE-2024-1",
            )
            await insert_ai_operation(
                db,
                operation_id="op-2",
                request_id=None,
                started_at="2026-07-10T12:01:00Z",
                latency_ms=99,
                feature="product_extraction",
                task_class="product_extraction",
                provider="gemini",
                model="gemini-2.0-flash-lite",
                success=False,
                error_class="empty",
                retry_index=1,
                fallback_from_provider="groq",
                fallback_from_model="openai/gpt-oss-20b",
                context_type="cve",
                context_id="CVE-2024-2",
            )
            await db.commit()
            assert await count_ai_operations(db) == 2
            rows = await list_ai_operations(db, limit=10)
            assert len(rows) == 2
            assert rows[0]["task_class"] == "product_extraction"
            assert rows[0]["error_class"] == "empty"
            assert rows[1]["provider"] == "groq"
            assert rows[1]["success"] in (True, 1)
        finally:
            await db.close()

    run_db_test(_run())


def test_usage_since_sums_tokens(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "ai_ops_tokens.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        from database import ai_operations_usage_since

        await init_db()
        db = await get_db()
        try:
            for i, (inp, out, tot) in enumerate([(10, 4, 14), (20, 6, 26)]):
                await insert_ai_operation(
                    db,
                    operation_id=f"tok-{i}",
                    request_id=None,
                    started_at=utcnow_str(),
                    latency_ms=10,
                    feature="pdf_summary",
                    task_class="pdf_summary",
                    provider="groq",
                    model="m",
                    success=True,
                    input_tokens=inp,
                    output_tokens=out,
                    total_tokens=tot,
                )
            await db.commit()
            usage = await ai_operations_usage_since(db, hours=24)
        finally:
            await db.close()
        return usage

    usage = run_db_test(_run())
    assert usage["total_tokens"] == 40
    assert usage["input_tokens"] == 30
    assert usage["output_tokens"] == 10
    assert usage["tokens_recorded"] is True


def test_models_catalog_payload_structure():
    payload = models_catalog_payload()
    assert payload["providers"] == ["groq", "gemini", "cerebras", "openrouter"]
    assert set(payload["tasks"]) == {
        "product_extraction",
        "pdf_summary",
        "detection_context",
    }
    for task_name, steps in payload["tasks"].items():
        chain = task_chain(task_name)  # type: ignore[arg-type]
        assert len(steps) == len(chain)
        assert steps[0]["order"] == 0
        assert steps[0]["provider"] == chain[0].provider
        assert steps[0]["model"] == chain[0].model


def test_admin_ai_operations_models_endpoint(admin_client):
    resp = admin_client.get("/api/admin/ai/operations/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "tasks" in data
    assert "pdf_summary" in data["tasks"]
