"""Model catalog SSOT for LLM task → provider failover chains (AI-1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from ai.gemini_client import gemini_model as _gemini_model
from ai.groq_config import GROQ_MODEL, GROQ_MODEL_SUMMARY
from ai.provider_catalog import catalog_status_rows, custom_provider_configured, custom_provider_step
from redact import mask_url_value

LLMTask = Literal["product_extraction", "pdf_summary", "detection_context"]

PROVIDER_ENV_KEYS = {
    "custom": "CUSTOM_LLM_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@dataclass(frozen=True)
class ProviderStep:
    provider: str
    model: str


def gemini_model() -> str:
    return _gemini_model()


def env_model(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


# OpenRouter :free defaults — Gemini Flash-Lite :free IDs were removed from the
# catalog (2026-07); use a live $0 model. Override via OPENROUTER_MODEL_*.
OPENROUTER_FREE_DEFAULT = "google/gemma-4-31b-it:free"


def openrouter_model(task: LLMTask) -> str:
    if task == "pdf_summary":
        return env_model("OPENROUTER_MODEL_PDF", OPENROUTER_FREE_DEFAULT)
    if task == "detection_context":
        return env_model("OPENROUTER_MODEL_DETECTION", OPENROUTER_FREE_DEFAULT)
    return env_model("OPENROUTER_MODEL_PRODUCT", OPENROUTER_FREE_DEFAULT)


def cerebras_model() -> str:
    return env_model("CEREBRAS_MODEL", "gpt-oss-120b")


def _scheduler_chain(task: LLMTask, *, groq_model: str) -> list[ProviderStep]:
    chain: list[ProviderStep] = []
    custom = custom_provider_step()
    if custom:
        chain.append(ProviderStep("custom", custom[2]))
    chain.extend([
        ProviderStep("groq", groq_model),
        ProviderStep("cerebras", cerebras_model()),
        ProviderStep("openrouter", openrouter_model(task)),
        ProviderStep("gemini", gemini_model()),
    ])
    return chain


def task_chain(task: LLMTask) -> list[ProviderStep]:
    """Failover order per task — not round-robin."""
    if task == "pdf_summary":
        return _scheduler_chain(task, groq_model=GROQ_MODEL_SUMMARY)
    return _scheduler_chain(task, groq_model=GROQ_MODEL)


def models_catalog_payload() -> dict:
    """Read-only catalog for admin API — no secrets."""
    tasks = {}
    for task in ("product_extraction", "pdf_summary", "detection_context"):
        tasks[task] = [
            {"provider": step.provider, "model": step.model, "order": idx}
            for idx, step in enumerate(task_chain(task))  # type: ignore[arg-type]
        ]
    custom = custom_provider_step()
    custom_url = (custom[0] if custom else os.environ.get("CUSTOM_LLM_BASE_URL", "")).rstrip("/")
    return {
        "providers": list(PROVIDER_ENV_KEYS.keys()),
        "tasks": tasks,
        "catalog": catalog_status_rows(),
        "custom_configured": custom_provider_configured(),
        "custom_base_url": mask_url_value(custom_url),
        "env_keys": {
            "groq_product": "GROQ_MODEL",
            "groq_summary": "GROQ_MODEL_SUMMARY",
            "gemini": "GEMINI_MODEL",
            "cerebras": "CEREBRAS_MODEL",
            "openrouter_pdf": "OPENROUTER_MODEL_PDF",
            "openrouter_product": "OPENROUTER_MODEL_PRODUCT",
            "openrouter_detection": "OPENROUTER_MODEL_DETECTION",
            "custom_base_url": "CUSTOM_LLM_BASE_URL",
            "custom_api_key": "CUSTOM_LLM_API_KEY",
            "custom_model": "CUSTOM_LLM_MODEL",
        },
    }
