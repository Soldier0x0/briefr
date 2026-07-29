"""AI anti-abuse rate caps and idempotency."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import llm_router as router
from ai.llm_router import chat_completion_task
from database import get_db, init_db
from tests.conftest import run_db_test


def test_idempotency_blocks_duplicate_cve(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("AI_DAILY_REQUEST_CAP", "9999")
    monkeypatch.setenv("AI_PER_MINUTE_CAP", "9999")
    calls = {"n": 0}

    async def fake_call(step, **_kwargs):
        calls["n"] += 1
        return "ok"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await init_db()
        first = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-0001",
        )
        second = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-0001",
        )
        return first, second, calls["n"]

    first, second, n = run_db_test(run())
    assert first is not None
    assert second is None
    assert n == 1


def test_daily_cap_blocks_llm_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ai_cap.db"))
    monkeypatch.setattr("database.DB_PATH", str(tmp_path / "ai_cap.db"))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("AI_DAILY_REQUEST_CAP", "1")
    monkeypatch.setenv("AI_PER_MINUTE_CAP", "100")

    async def fake_call(step, **_kwargs):
        return "ok"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        from db.ai_operations import insert_ai_operation
        await init_db()
        db = await get_db()
        try:
            await insert_ai_operation(
                db,
                operation_id="op-1",
                request_id=None,
                started_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                latency_ms=1,
                feature="llm",
                task_class="product_extraction",
                provider="groq",
                model="m",
                success=True,
            )
            await db.commit()
        finally:
            await db.close()
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-9999",
        )

    assert run_db_test(run()) is None


def test_idempotency_allows_retry_after_failed_attempt(monkeypatch):
    router._recent_task_context.clear()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("AI_DAILY_REQUEST_CAP", "9999")
    monkeypatch.setenv("AI_PER_MINUTE_CAP", "9999")
    calls = {"n": 0}

    async def fake_call(step, **_kwargs):
        calls["n"] += 1
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await init_db()
        first = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-0002",
        )
        second = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-0002",
        )
        return first, second, calls["n"]

    first, second, n = run_db_test(run())
    assert first is None
    assert second is None
    assert n >= 2


def test_quota_fail_closed_when_usage_unreadable(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("AI_DAILY_REQUEST_CAP", "9999")
    monkeypatch.setenv("AI_PER_MINUTE_CAP", "9999")

    async def fail_count(*_args, **_kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("db.ai_operations.count_ai_operations_since", fail_count)

    async def run():
        from tracking import has_ai_request_quota
        return await has_ai_request_quota()

    assert run_db_test(run()) is False
