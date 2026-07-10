"""Model catalog SSOT for LLM task → provider failover chains (AI-1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from ai.gemini_client import gemini_model as _gemini_model
from ai.groq_config import GROQ_MODEL, GROQ_MODEL_SUMMARY

LLMTask = Literal["product_extraction", "pdf_summary", "detection_context"]

PROVIDER_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class ProviderStep:
    provider: str
    model: str


def gemini_model() -> str:
    return _gemini_model()


def env_model(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


def openrouter_model(task: LLMTask) -> str:
    if task == "pdf_summary":
        return env_model(
            "OPENROUTER_MODEL_PDF",
            "google/gemini-2.0-flash-lite-001:free",
        )
    if task == "detection_context":
        return env_model(
            "OPENROUTER_MODEL_DETECTION",
            "google/gemini-2.0-flash-lite-001:free",
        )
    return env_model(
        "OPENROUTER_MODEL_PRODUCT",
        "google/gemini-2.0-flash-lite-001:free",
    )


def cerebras_model() -> str:
    return env_model("CEREBRAS_MODEL", "gpt-oss-120b")


def task_chain(task: LLMTask) -> list[ProviderStep]:
    """Failover order per task — not round-robin."""
    if task == "detection_context":
        return [
            ProviderStep("groq", GROQ_MODEL),
            ProviderStep("gemini", gemini_model()),
            ProviderStep("openrouter", openrouter_model(task)),
        ]
    if task == "pdf_summary":
        return [
            ProviderStep("groq", GROQ_MODEL_SUMMARY),
            ProviderStep("gemini", gemini_model()),
            ProviderStep("cerebras", cerebras_model()),
            ProviderStep("openrouter", openrouter_model(task)),
        ]
    return [
        ProviderStep("groq", GROQ_MODEL),
        ProviderStep("gemini", gemini_model()),
        ProviderStep("cerebras", cerebras_model()),
        ProviderStep("openrouter", openrouter_model(task)),
    ]


def models_catalog_payload() -> dict:
    """Read-only catalog for admin API — no secrets."""
    tasks = {}
    for task in ("product_extraction", "pdf_summary", "detection_context"):
        tasks[task] = [
            {"provider": step.provider, "model": step.model, "order": idx}
            for idx, step in enumerate(task_chain(task))  # type: ignore[arg-type]
        ]
    return {
        "providers": list(PROVIDER_ENV_KEYS.keys()),
        "tasks": tasks,
        "env_keys": {
            "groq_product": "GROQ_MODEL",
            "groq_summary": "GROQ_MODEL_SUMMARY",
            "gemini": "GEMINI_MODEL",
            "cerebras": "CEREBRAS_MODEL",
            "openrouter_pdf": "OPENROUTER_MODEL_PDF",
            "openrouter_product": "OPENROUTER_MODEL_PRODUCT",
            "openrouter_detection": "OPENROUTER_MODEL_DETECTION",
        },
    }
