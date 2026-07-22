"""Task-based multi-provider LLM router with failover (Track K2).

Failover order per task — not round-robin. One attempt per provider per call;
never parallel-call the same CVE on multiple providers.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Callable, Literal

from ai.gemini_client import gemini_chat_completion
from ai.groq_config import GROQ_URL, scheduler_llm_timeout
from ai.llm_payload import has_llm_request_payload
from ai.llm_session import (
    is_provider_skipped_in_job,
    mark_provider_empty_response,
    provider_circuit_open,
)
from ai.model_catalog import ProviderStep, task_chain
from ai.model_catalog import gemini_model as gemini_model  # re-export for tests
from ai.openai_chat import openai_chat_completion
from ai.operations_recorder import AttemptTimer, classify_llm_error, record_llm_attempt
from api_queue_operations import LLM_TASK_OPERATIONS
from database import get_db
from db.ai_operation_payloads import (
    insert_ai_operation_payload,
    store_failure_payloads_enabled,
)
from resilient_client import CircuitOpenError, record_source_success

logger = logging.getLogger(__name__)

LLMTask = Literal["product_extraction", "pdf_summary", "detection_context"]

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_PROVIDER_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    provider: str
    model: str


def _task_chain(task: LLMTask) -> list[ProviderStep]:
    """Backward-compatible alias — SSOT is ai.model_catalog.task_chain."""
    return task_chain(task)


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
    queue_operation: str,
    queue_context_type: str | None = None,
    queue_context_id: str | None = None,
    usage_out: dict | None = None,
) -> str:
    api_key = _api_key(step.provider)
    if not api_key:
        return ""

    queue_kwargs = {
        "queue_operation": queue_operation,
        "queue_context_type": queue_context_type,
        "queue_context_id": queue_context_id,
        "usage_out": usage_out,
    }

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
            **queue_kwargs,
        )

    if step.provider == "gemini":
        return await gemini_chat_completion(
            api_key,
            messages=messages,
            model=step.model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            **queue_kwargs,
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
            **queue_kwargs,
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
            **queue_kwargs,
        )

    return ""


async def _record_attempt(
    *,
    task: LLMTask,
    step: ProviderStep,
    timer: AttemptTimer,
    success: bool,
    retry_index: int,
    queue_context_type: str,
    queue_context_id: str,
    error_class: str | None = None,
    fallback_from_provider: str | None = None,
    fallback_from_model: str | None = None,
    usage: dict | None = None,
) -> str | None:
    usage = usage or {}
    return await record_llm_attempt(
        task=task,
        provider=step.provider,
        model=step.model,
        success=success,
        latency_ms=timer.elapsed_ms(),
        retry_index=retry_index,
        context_type=queue_context_type,
        context_id=queue_context_id,
        error_class=error_class,
        fallback_from_provider=fallback_from_provider,
        fallback_from_model=fallback_from_model,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


async def _store_failure_payload(
    *,
    operation_id: str | None,
    messages: list[dict[str, str]],
    response_excerpt: str | None,
    task: LLMTask,
    step: ProviderStep,
) -> None:
    if not operation_id or not store_failure_payloads_enabled():
        return
    db = await get_db()
    try:
        await insert_ai_operation_payload(
            db,
            operation_id=operation_id,
            messages_json=json.dumps(messages, ensure_ascii=True),
            response_excerpt=response_excerpt,
            task_class=task,
            provider=step.provider,
            model=step.model,
        )
        await db.commit()
    except Exception:
        logger.warning("Failed to record ai_operation_payloads row", exc_info=True)
    finally:
        await db.close()


async def chat_completion_task(
    task: LLMTask,
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float | None = None,
    cve_id: str | None = None,
    on_provider_attempt: Callable[[str], None] | None = None,
    context_type: str | None = None,
    context_id: str | None = None,
    ignore_provider_circuit: bool = False,
) -> LLMCompletion | None:
    """Try providers in failover order; return first non-empty completion."""
    if timeout is None:
        timeout = scheduler_llm_timeout()
    if not has_llm_request_payload(messages):
        logger.info(
            "Skipping LLM task %s — no outbound user/assistant payload (cve=%s)",
            task,
            cve_id or "—",
        )
        return None

    queue_operation = LLM_TASK_OPERATIONS.get(task, "outbound_request")
    queue_context_type = context_type if context_type is not None else ("cve" if cve_id else "task")
    queue_context_id = context_id if context_id is not None else (cve_id if cve_id else task)

    attempt_index = 0
    last_failed_provider: str | None = None
    last_failed_model: str | None = None

    from tracking import has_quota

    for step in _task_chain(task):
        if not _api_key(step.provider):
            continue

        if not await has_quota(step.provider):
            logger.info(
                "Skipping LLM provider %s for task %s — quota exhausted",
                step.provider,
                task,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
            continue
        if is_provider_skipped_in_job(step.provider):
            logger.info(
                "Skipping LLM provider %s for task %s — empty response earlier in this job",
                step.provider,
                task,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
            continue
        if (not ignore_provider_circuit) and provider_circuit_open(step.provider):
            logger.info(
                "Skipping LLM provider %s for task %s — circuit open",
                step.provider,
                task,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
            continue
        if on_provider_attempt:
            try:
                on_provider_attempt(step.provider)
            except Exception:
                pass
        timer = AttemptTimer()
        usage: dict = {}
        try:
            content = (
                await _call_provider(
                    step,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                    queue_operation=queue_operation,
                    queue_context_type=queue_context_type,
                    queue_context_id=queue_context_id,
                    usage_out=usage,
                )
            ).strip()
            if content:
                record_source_success(step.provider)
                await _record_attempt(
                    task=task,
                    step=step,
                    timer=timer,
                    success=True,
                    retry_index=attempt_index,
                    queue_context_type=queue_context_type,
                    queue_context_id=queue_context_id,
                    fallback_from_provider=last_failed_provider,
                    fallback_from_model=last_failed_model,
                    usage=usage,
                )
                return LLMCompletion(
                    content=content,
                    provider=step.provider,
                    model=step.model,
                )
            logger.warning("LLM %s returned empty content for task %s", step.provider, task)
            mark_provider_empty_response(step.provider)
            operation_id = await _record_attempt(
                task=task,
                step=step,
                timer=timer,
                success=False,
                retry_index=attempt_index,
                queue_context_type=queue_context_type,
                queue_context_id=queue_context_id,
                error_class=classify_llm_error(None, empty=True),
            )
            await _store_failure_payload(
                operation_id=operation_id,
                messages=messages,
                response_excerpt="",
                task=task,
                step=step,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
        except CircuitOpenError as exc:
            logger.warning(
                "LLM circuit open for %s (task %s) — trying next provider: %s",
                step.provider,
                task,
                exc,
            )
            operation_id = await _record_attempt(
                task=task,
                step=step,
                timer=timer,
                success=False,
                retry_index=attempt_index,
                queue_context_type=queue_context_type,
                queue_context_id=queue_context_id,
                error_class=classify_llm_error(exc),
            )
            await _store_failure_payload(
                operation_id=operation_id,
                messages=messages,
                response_excerpt=str(exc),
                task=task,
                step=step,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
        except Exception as exc:
            logger.warning(
                "LLM %s failed for task %s — trying next provider: %s",
                step.provider,
                task,
                exc,
            )
            operation_id = await _record_attempt(
                task=task,
                step=step,
                timer=timer,
                success=False,
                retry_index=attempt_index,
                queue_context_type=queue_context_type,
                queue_context_id=queue_context_id,
                error_class=classify_llm_error(exc),
            )
            await _store_failure_payload(
                operation_id=operation_id,
                messages=messages,
                response_excerpt=str(exc),
                task=task,
                step=step,
            )
            last_failed_provider = step.provider
            last_failed_model = step.model
            attempt_index += 1
    return None
