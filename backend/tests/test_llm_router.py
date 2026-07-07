"""Tests for multi-provider LLM router (Track K2)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai import llm_router as router
from ai.llm_router import LLMCompletion, chat_completion_task
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


def test_task_chain_detection_context_omits_cerebras(monkeypatch):
    chain = router._task_chain("detection_context")
    providers = [step.provider for step in chain]
    assert providers == ["groq", "gemini", "openrouter"]


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
