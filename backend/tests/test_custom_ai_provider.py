"""Custom AI provider catalog and router integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.model_catalog import task_chain
from ai.provider_catalog import catalog_status_rows, custom_provider_configured, validate_model_name
from tests.conftest import run_db_test


def test_model_name_regex():
    assert validate_model_name("gpt-4o-mini")
    assert not validate_model_name("bad model")


def test_custom_provider_prepended(monkeypatch):
    monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "https://llm.example/v1/chat/completions")
    monkeypatch.setenv("CUSTOM_LLM_API_KEY", "sk-custom")
    monkeypatch.setenv("CUSTOM_LLM_MODEL", "my-model")
    assert task_chain("product_extraction")[0].provider == "custom"


def test_catalog_status_includes_custom():
    assert any(r["id"] == "custom" for r in catalog_status_rows())


def test_custom_openai_completion(monkeypatch):
    monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("CUSTOM_LLM_API_KEY", "sk-custom")
    monkeypatch.setenv("CUSTOM_LLM_MODEL", "my-model")

    async def fake_openai(**kwargs):
        return "custom answer"

    from ai import llm_router
    from ai.model_catalog import ProviderStep

    monkeypatch.setattr(llm_router, "openai_chat_completion", fake_openai)

    async def run():
        return await llm_router._call_provider(
            ProviderStep("custom", "my-model"),
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            temperature=0.0,
            timeout=10.0,
            queue_operation="test",
        )

    assert run_db_test(run()) == "custom answer"
