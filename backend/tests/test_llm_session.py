"""Tests for per-job LLM provider session and empty-response degradation."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import llm_router as router
from ai.llm_router import LLMCompletion, chat_completion_task
from ai.llm_session import llm_job_session
from resilient_client import get_feed_health, reset_feed_health
from tests.conftest import run_db_test


def _reset_llm_router_state(monkeypatch) -> None:
    """Isolate tests from shared idempotency cache and rate caps."""
    router._recent_task_context.clear()
    monkeypatch.setenv("AI_DAILY_REQUEST_CAP", "9999")
    monkeypatch.setenv("AI_PER_MINUTE_CAP", "9999")
    for key in ("CUSTOM_LLM_BASE_URL", "CUSTOM_LLM_API_KEY", "CUSTOM_LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
def test_empty_response_failsover_within_single_call(monkeypatch):
    _reset_llm_router_state(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
    reset_feed_health()

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "groq":
            return ""
        return "gemini answer"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "extract products from text"}],
            cve_id="CVE-2024-0001",
        )

    result = run_db_test(run())
    assert result == LLMCompletion(
        content="gemini answer",
        provider="gemini",
        model=router.gemini_model(),
    )
    assert calls == ["groq", "gemini"]
    health = get_feed_health().get("groq", {})
    assert health.get("consecutive_failures", 0) >= 1


def test_job_session_skips_empty_provider_on_later_calls(monkeypatch):
    _reset_llm_router_state(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
    reset_feed_health()

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "groq":
            return ""
        return f"{step.provider} answer"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        with llm_job_session():
            first = await chat_completion_task(
                "product_extraction",
                messages=[{"role": "user", "content": "extract products from text"}],
                cve_id="CVE-2024-0001",
            )
            second = await chat_completion_task(
                "product_extraction",
                messages=[{"role": "user", "content": "extract products from text"}],
                cve_id="CVE-2024-0002",
            )
        return first, second

    first, second = run_db_test(run())
    assert first is not None
    assert second is not None
    assert first.provider == "gemini"
    assert second.provider == "gemini"
    # First CVE: groq then gemini. Second CVE: groq skipped, gemini only.
    assert calls == ["groq", "gemini", "gemini"]


def test_without_job_session_retries_primary_each_call(monkeypatch):
    _reset_llm_router_state(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
    reset_feed_health()

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        if step.provider == "groq":
            return ""
        return "gemini answer"

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "extract products from text"}],
            cve_id="CVE-2024-0001",
        )
        await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "extract products from text"}],
            cve_id="CVE-2024-0002",
        )

    run_db_test(run())
    assert calls == ["groq", "gemini", "groq", "gemini"]


def test_circuit_open_skips_provider_without_http(monkeypatch):
    _reset_llm_router_state(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")

    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        return "gemini answer"

    monkeypatch.setattr(router, "_call_provider", fake_call)
    monkeypatch.setattr(router, "provider_circuit_open", lambda provider: provider == "groq")

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "extract products from text"}],
        )

    result = run_db_test(run())
    assert result is not None
    assert result.provider == "gemini"
    assert calls == ["gemini"]
