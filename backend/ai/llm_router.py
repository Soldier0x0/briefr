"""Task-based multi-provider LLM router with failover (Track K2).

Failover order per task — not round-robin. One attempt per provider per call;
never parallel-call the same CVE on multiple providers.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from ai.gemini_client import gemini_chat_completion, gemini_model
from ai.groq_config import GROQ_MODEL, GROQ_MODEL_SUMMARY, GROQ_URL
from ai.openai_chat import openai_chat_completion
from resilient_client import CircuitOpenError

logger = logging.getLogger(__name__)

LLMTask = Literal["product_extraction", "pdf_summary"]

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_PROVIDER_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class ProviderStep:
    provider: str
    model: str


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    provider: str
    model: str


def _env_model(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


def _openrouter_free_model(task: LLMTask) -> str:
    if task == "pdf_summary":
        return _env_model(
            "OPENROUTER_MODEL_PDF",
            "google/gemini-2.0-flash-lite-001:free",
        )
    return _env_model(
        "OPENROUTER_MODEL_PRODUCT",
        "google/gemini-2.0-flash-lite-001:free",
    )


def _task_chain(task: LLMTask) -> list[ProviderStep]:
    cerebras_model = _env_model("CEREBRAS_MODEL", "gpt-oss-120b")
    if task == "pdf_summary":
        return [
            ProviderStep("groq", GROQ_MODEL_SUMMARY),
            ProviderStep("gemini", gemini_model()),
            ProviderStep("cerebras", cerebras_model),
            ProviderStep("openrouter", _openrouter_free_model(task)),
        ]
    return [
        ProviderStep("groq", GROQ_MODEL),
        ProviderStep("gemini", gemini_model()),
        ProviderStep("cerebras", cerebras_model),
        ProviderStep("openrouter", _openrouter_free_model(task)),
    ]


def any_llm_provider_configured() -> bool:
    return bool(get_configured_providers())


_PLACEHOLDER_KEY_MARKERS = ("your_key_here", "your_api_key_here", "your_key")


def _is_usable_api_key(value: str) -> bool:
    val = (value or "").strip()
    if not val:
        return False
    lowered = val.lower()
    if lowered in _PLACEHOLDER_KEY_MARKERS or lowered.startswith("your_"):
        return False
    if "placeholder" in lowered:
        return False
    return True


def get_configured_providers() -> list[str]:
    out: list[str] = []
    for provider in _PROVIDER_ENV_KEYS:
        if _api_key(provider):
            out.append(provider)
    return out


def _api_key(provider: str) -> str:
    env_key = _PROVIDER_ENV_KEYS.get(provider, "")
    val = os.environ.get(env_key, "").strip() if env_key else ""
    return val if _is_usable_api_key(val) else ""


async def _call_provider(
    step: ProviderStep,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> str:
    api_key = _api_key(step.provider)
    if not api_key:
        return ""

    if step.provider == "groq":
        return await openai_chat_completion(
            source="groq",
            url=GROQ_URL,
            api_key=api_key,
            model=step.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    if step.provider == "gemini":
        return await gemini_chat_completion(
            api_key,
            messages=messages,
            model=step.model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    if step.provider == "cerebras":
        return await openai_chat_completion(
            source="cerebras",
            url=CEREBRAS_URL,
            api_key=api_key,
            model=step.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    if step.provider == "openrouter":
        return await openai_chat_completion(
            source="openrouter",
            url=OPENROUTER_URL,
            api_key=api_key,
            model=step.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            extra_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://briefr.local"),
                "X-Title": "BRIEFR",
            },
        )

    return ""


async def chat_completion_task(
    task: LLMTask,
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> LLMCompletion | None:
    """Try providers in failover order; return first non-empty completion."""
    for step in _task_chain(task):
        if not _api_key(step.provider):
            continue
        try:
            content = (
                await _call_provider(
                    step,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
            ).strip()
            if content:
                return LLMCompletion(
                    content=content,
                    provider=step.provider,
                    model=step.model,
                )
            logger.warning("LLM %s returned empty content for task %s", step.provider, task)
        except CircuitOpenError as exc:
            logger.warning(
                "LLM circuit open for %s (task %s) — trying next provider: %s",
                step.provider,
                task,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "LLM %s failed for task %s — trying next provider: %s",
                step.provider,
                task,
                exc,
            )
    return None
