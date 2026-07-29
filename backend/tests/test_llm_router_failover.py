"""LLM provider timeout failover (Phase E2)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import llm_router as router
from ai.llm_router import LLMCompletion, chat_completion_task, llm_provider_timeout
from tests.conftest import run_db_test


def test_llm_provider_timeout_respects_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_TIMEOUT_SEC", "45")
    assert llm_provider_timeout() == 45.0


def test_chat_completion_failover_on_timeout(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    calls: list[str] = []

    async def fake_call(step, **_kwargs):
        calls.append(step.provider)
        return "gemini ok" if step.provider == "gemini" else ""

    n = {"v": 0}

    async def selective_wait_for(coro, *, timeout):
        n["v"] += 1
        if n["v"] == 1:
            coro.close()
            raise asyncio.TimeoutError()
        return await coro

    monkeypatch.setattr(router.asyncio, "wait_for", selective_wait_for)
    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        return await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hi"}],
            cve_id="CVE-2024-TIMEOUT-TEST",
        )

    result = run_db_test(run())
    assert isinstance(result, LLMCompletion)
    assert result.provider == "gemini"
