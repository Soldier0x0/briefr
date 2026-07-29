"""Admin AI operations APIs (AI-2)."""

from __future__ import annotations

import json
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
    insert_ai_operation_payload,
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


def test_providers_payload_lists_five_providers():
    payload = build_providers_payload()
    names = [p["provider"] for p in payload["providers"]]
    assert names == ["custom", "groq", "cerebras", "openrouter", "gemini"]
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
            await insert_ai_operation_payload(
                db,
                operation_id="u1",
                messages_json=json.dumps([{"role": "user", "content": "hello"}]),
                response_excerpt="timeout",
                task_class="pdf_summary",
                provider="groq",
                model="m1",
            )
            await db.commit()
            usage = await ai_operations_usage_since(db, hours=24 * 365)
            assert usage["total"] == 2
            assert usage["failures"] == 1
            rows, total = await list_ai_operations_page(db, limit=1, offset=0)
            assert total == 2
            assert len(rows) == 1
            all_rows, _ = await list_ai_operations_page(db, limit=10, offset=0)
            by_operation_id = {row["operation_id"]: row for row in all_rows}
            assert by_operation_id["u1"]["has_payload"] is True
            assert by_operation_id["u1"]["payload_actionable"] is False
            assert by_operation_id["u2"]["has_payload"] is False
            assert by_operation_id["u2"]["payload_actionable"] is False
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
    assert len(providers.json()["providers"]) == 5

    activity = admin_client.get("/api/admin/ai/operations/activity?limit=10&offset=0")
    assert activity.status_code == 200
    assert "rows" in activity.json()
    assert "total" in activity.json()


def _seed_failure_payload(operation_id: str) -> None:
    async def _seed():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation_payload(
                db,
                operation_id=operation_id,
                messages_json=json.dumps(
                    [
                        {"role": "system", "content": "You are a helper"},
                        {"role": "user", "content": "Summarize this CVE"},
                    ]
                ),
                response_excerpt="provider timeout",
                task_class="pdf_summary",
                provider="groq",
                model="llama-3.1-8b-instant",
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())


def _seed_activity_operation_with_payload(operation_id: str) -> None:
    async def _seed():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation(
                db,
                operation_id=operation_id,
                request_id=None,
                started_at="2099-01-01T00:00:00Z",
                latency_ms=15,
                feature="pdf_summary",
                task_class="pdf_summary",
                provider="groq",
                model="m1",
                success=False,
                error_class="empty",
            )
            await insert_ai_operation_payload(
                db,
                operation_id=operation_id,
                messages_json=json.dumps([{"role": "user", "content": "test payload"}]),
                response_excerpt="empty response",
                task_class="pdf_summary",
                provider="groq",
                model="m1",
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(_seed())


def test_get_payload_404_when_missing(admin_client):
    r = admin_client.get("/api/admin/ai/operations/nope/payload")
    assert r.status_code == 404


def test_activity_endpoint_includes_has_payload_boolean(admin_client):
    operation_id = "op-activity-payload-1"
    _seed_activity_operation_with_payload(operation_id)

    r = admin_client.get("/api/admin/ai/operations/activity?limit=10&offset=0")
    assert r.status_code == 200
    rows = r.json()["rows"]
    matching = [row for row in rows if row["operation_id"] == operation_id]
    assert matching
    assert matching[0]["has_payload"] is True
    assert matching[0]["payload_actionable"] is True


def test_payload_actionable_false_when_context_already_succeeded(tmp_path, monkeypatch):
    db_path = tmp_path / "ai_ops_resolved.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    context_type = "payload"
    context_id = "payload-hash-abc"

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation(
                db,
                operation_id="op-fail-provider-a",
                request_id=None,
                started_at="2099-01-02T00:00:00Z",
                latency_ms=12,
                feature="product_extraction",
                task_class="product_extraction",
                provider="groq",
                model="m1",
                success=False,
                error_class="empty",
                context_type=context_type,
                context_id=context_id,
            )
            await insert_ai_operation_payload(
                db,
                operation_id="op-fail-provider-a",
                messages_json=json.dumps([{"role": "user", "content": "x"}]),
                response_excerpt="empty",
                task_class="product_extraction",
                provider="groq",
                model="m1",
            )
            await insert_ai_operation(
                db,
                operation_id="op-ok-provider-b",
                request_id=None,
                started_at="2099-01-02T00:00:01Z",
                latency_ms=8,
                feature="product_extraction",
                task_class="product_extraction",
                provider="cerebras",
                model="m2",
                success=True,
                context_type=context_type,
                context_id=context_id,
            )
            await db.commit()
            rows, _ = await list_ai_operations_page(db, limit=10, offset=0)
            by_id = {row["operation_id"]: row for row in rows}
            assert by_id["op-fail-provider-a"]["has_payload"] is True
            assert by_id["op-fail-provider-a"]["payload_actionable"] is False
            assert by_id["op-ok-provider-b"]["payload_actionable"] is False
        finally:
            await db.close()

    run_db_test(_run())


def test_payload_actionable_still_true_for_task_level_context(tmp_path, monkeypatch):
    """Generic task context (task/product_extraction) must not hide retry on unrelated failures."""
    db_path = tmp_path / "ai_ops_task_ctx.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation(
                db,
                operation_id="op-task-ok",
                request_id=None,
                started_at="2099-01-03T00:00:00Z",
                latency_ms=5,
                feature="product_extraction",
                task_class="product_extraction",
                provider="cerebras",
                model="m1",
                success=True,
                context_type="task",
                context_id="product_extraction",
            )
            await insert_ai_operation(
                db,
                operation_id="op-task-fail",
                request_id=None,
                started_at="2099-01-03T00:00:01Z",
                latency_ms=12,
                feature="product_extraction",
                task_class="product_extraction",
                provider="groq",
                model="m2",
                success=False,
                error_class="empty",
                context_type="task",
                context_id="product_extraction",
            )
            await insert_ai_operation_payload(
                db,
                operation_id="op-task-fail",
                messages_json=json.dumps([{"role": "user", "content": "y"}]),
                response_excerpt="empty",
                task_class="product_extraction",
                provider="groq",
                model="m2",
            )
            await db.commit()
            rows, _ = await list_ai_operations_page(db, limit=10, offset=0)
            by_id = {row["operation_id"]: row for row in rows}
            assert by_id["op-task-fail"]["payload_actionable"] is True
        finally:
            await db.close()

    run_db_test(_run())


def test_get_payload_returns_stored_payload(admin_client):
    operation_id = "op-payload-1"
    _seed_failure_payload(operation_id)

    r = admin_client.get(f"/api/admin/ai/operations/{operation_id}/payload")
    assert r.status_code == 200
    body = r.json()
    assert body["operation_id"] == operation_id
    assert body["task_class"] == "pdf_summary"
    assert body["provider"] == "groq"
    assert body["model"] == "llama-3.1-8b-instant"
    assert body["response_excerpt"] == "provider timeout"
    assert isinstance(body["messages"], list)
    assert body["messages"][0]["role"] == "system"
    assert body["created_at"]


def test_retry_replays_stored_messages(admin_client, monkeypatch):
    operation_id = "op-retry-1"
    _seed_failure_payload(operation_id)

    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    async def _fake_call_provider(_step, **_kwargs):
        return "Replay successful"

    monkeypatch.setattr("ai.llm_router._call_provider", _fake_call_provider)

    r = admin_client.post(f"/api/admin/ai/operations/{operation_id}/retry")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    replay_operation_id = body["replay_operation_id"]
    assert replay_operation_id
    assert body["provider"] == "groq"
    assert body["error_class"] is None

    activity = admin_client.get("/api/admin/ai/operations/activity?limit=25&offset=0")
    assert activity.status_code == 200
    rows = activity.json()["rows"]
    replay_rows = [row for row in rows if row["operation_id"] == replay_operation_id]
    assert replay_rows
    assert replay_rows[0]["context_type"] == "replay"
    assert replay_rows[0]["context_id"] == operation_id

    audit = admin_client.get("/api/admin/audit-log?limit=20&action=ai.operations.retry")
    assert audit.status_code == 200
    audit_rows = audit.json()["rows"]
    assert any(row.get("target") == operation_id for row in audit_rows)


def test_retry_returns_409_when_circuit_open_unless_forced(admin_client, monkeypatch):
    operation_id = "op-retry-force-1"
    _seed_failure_payload(operation_id)

    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")

    async def _fake_call_provider(_step, **_kwargs):
        return "forced replay successful"

    monkeypatch.setattr("ai.llm_router._call_provider", _fake_call_provider)
    monkeypatch.setattr("routers.admin.ai_ops.provider_circuit_open", lambda _provider: True)

    blocked = admin_client.post(f"/api/admin/ai/operations/{operation_id}/retry")
    assert blocked.status_code == 409
    assert "force=true" in blocked.json().get("detail", "")

    forced = admin_client.post(
        f"/api/admin/ai/operations/{operation_id}/retry",
        json={"force": True},
    )
    assert forced.status_code == 200
    assert forced.json()["success"] is True
