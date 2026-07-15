"""Tests for multi-provider LLM router (Track K2)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import llm_router as router
from ai.llm_router import LLMCompletion, chat_completion_task
from db.config import is_postgres
from resilient_client import CircuitOpenError


def test_get_configured_providers_reads_env(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test")
    assert router.get_configured_providers() == ["cerebras", "openrouter"]


def test_any_llm_provider_configured_false_without_keys(monkeypatch):
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert router.any_llm_provider_configured() is False


def test_placeholder_keys_are_ignored(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "your_key_here")
    monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")
    assert router.get_configured_providers() == []
    assert router.any_llm_provider_configured() is False


def test_task_chain_pdf_summary_uses_summary_groq_model(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_SUMMARY", "openai/gpt-oss-120b")
    chain = router._task_chain("pdf_summary")
    assert chain[0].provider == "groq"
    assert chain[0].model == "openai/gpt-oss-120b"


def test_task_chain_product_extraction_uses_default_groq_model(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    chain = router._task_chain("product_extraction")
    assert chain[0].provider == "groq"
    assert chain[0].model == "openai/gpt-oss-20b"


def test_task_chain_detection_context_includes_cerebras(monkeypatch):
    chain = router._task_chain("detection_context")
    providers = [step.provider for step in chain]
    assert providers == ["groq", "gemini", "cerebras", "openrouter"]


def test_chat_completion_task_skips_empty_payload(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        return "should not run"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "system", "content": "instructions only"}],
        )

    assert asyncio.run(run()) is None
    assert calls == []


def test_chat_completion_task_failover_skips_missing_keys(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "gemini":
            return "gemini answer"
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
        )

    result = asyncio.run(run())
    assert result == LLMCompletion(content="gemini answer", provider="gemini", model=router.gemini_model())
    assert calls == ["gemini"]


def test_chat_completion_task_failover_on_provider_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "groq":
            raise RuntimeError("groq down")
        if step.provider == "gemini":
            return "backup answer"
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
        )

    result = asyncio.run(run())
    assert result == LLMCompletion(
        content="backup answer",
        provider="gemini",
        model=router.gemini_model(),
    )
    assert calls == ["groq", "gemini"]


def test_chat_completion_task_failover_on_circuit_open(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")

    async def fake_call(step, **_kwargs):
        if step.provider == "groq":
            raise CircuitOpenError("groq", retry_at=0.0)
        if step.provider == "cerebras":
            return "cerebras answer"
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
        )

    result = asyncio.run(run())
    assert result is not None
    assert result.provider == "cerebras"
    assert result.content == "cerebras answer"


def test_chat_completion_task_returns_none_when_all_fail(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    async def fake_call(_step, **_kwargs):
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
        )

    assert asyncio.run(run()) is None


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.headers = {}

    def json(self):
        return self._payload


def test_openai_chat_skips_empty_payload(monkeypatch):
    import ai.openai_chat as oc

    called = {"n": 0}

    async def fake_request(*_a, **_k):
        called["n"] += 1
        raise AssertionError("resilient_request should not run")

    monkeypatch.setattr(oc, "resilient_request", fake_request)

    async def run():
        return await oc.openai_chat_completion(
            source="groq",
            url="http://x",
            api_key="k",
            model="m",
            messages=[{"role": "system", "content": "only"}],
        )

    assert asyncio.run(run()) == ""
    assert called["n"] == 0


def test_openai_chat_populates_usage_out(monkeypatch):
    import ai.openai_chat as oc

    async def fake_request(*_a, **_k):
        return _FakeResponse(
            {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            }
        )

    monkeypatch.setattr(oc, "resilient_request", fake_request)
    monkeypatch.setattr(oc, "apply_rate_limit_headers", lambda *a, **k: None)

    usage: dict = {}

    async def run():
        return await oc.openai_chat_completion(
            source="groq",
            url="http://x",
            api_key="k",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            usage_out=usage,
        )

    content = asyncio.run(run())
    assert content == "hello"
    assert usage == {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}


def test_gemini_chat_skips_empty_payload(monkeypatch):
    import ai.gemini_client as gc

    called = {"n": 0}

    async def fake_request(*_a, **_k):
        called["n"] += 1
        raise AssertionError("resilient_request should not run")

    monkeypatch.setattr(gc, "resilient_request", fake_request)

    async def run():
        return await gc.gemini_chat_completion(
            "k",
            messages=[{"role": "user", "content": ""}],
        )

    assert asyncio.run(run()) == ""
    assert called["n"] == 0


def test_gemini_chat_populates_usage_out(monkeypatch):
    import ai.gemini_client as gc

    async def fake_request(*_a, **_k):
        return _FakeResponse(
            {
                "candidates": [{"content": {"parts": [{"text": "hi there"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 8,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 11,
                },
            }
        )

    monkeypatch.setattr(gc, "resilient_request", fake_request)
    monkeypatch.setattr(gc, "apply_rate_limit_headers", lambda *a, **k: None)

    usage: dict = {}

    async def run():
        return await gc.gemini_chat_completion(
            "k",
            messages=[{"role": "user", "content": "hi"}],
            usage_out=usage,
        )

    content = asyncio.run(run())
    assert content == "hi there"
    assert usage == {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}


def test_chat_completion_task_records_token_usage(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "llm_router_tokens.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    async def fake_call(step, **kwargs):
        out = kwargs.get("usage_out")
        if out is not None:
            out.update({"input_tokens": 30, "output_tokens": 12, "total_tokens": 42})
        return "answer"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        from database import get_db, init_db, list_ai_operations

        await init_db()
        await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
        )
        db = await get_db()
        try:
            rows = await list_ai_operations(db, limit=5)
        finally:
            await db.close()
        return rows

    rows = asyncio.run(run())
    assert len(rows) == 1
    assert rows[0]["total_tokens"] == 42
    assert rows[0]["input_tokens"] == 30
    assert rows[0]["output_tokens"] == 12


def test_chat_completion_task_records_operations(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "llm_router_ops.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")

    async def fake_call(step, **_kwargs):
        if step.provider == "groq":
            raise RuntimeError("groq down")
        if step.provider == "gemini":
            return "backup answer"
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        from database import count_ai_operations, get_db, init_db, list_ai_operations

        await init_db()
        result = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-9999",
        )
        db = await get_db()
        try:
            count = await count_ai_operations(db)
            rows = await list_ai_operations(db, limit=10)
        finally:
            await db.close()
        return result, count, rows

    result, count, rows = asyncio.run(run())
    assert result is not None
    assert result.provider == "gemini"
    assert count == 2
    by_provider = {row["provider"]: row for row in rows}
    assert by_provider["groq"]["success"] in (False, 0)
    assert by_provider["groq"]["error_class"] == "unknown"
    assert by_provider["gemini"]["success"] in (True, 1)
    assert by_provider["gemini"]["retry_index"] == 1

