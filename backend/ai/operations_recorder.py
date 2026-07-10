"""Record LLM completion attempts to ai_operations (AI-1)."""

from __future__ import annotations

import logging
import os
import uuid
from time import monotonic

from database import get_db, insert_ai_operation
from db.timeutil import utcnow_str
from resilient_client import CircuitOpenError
from structured_logging import request_id_var

logger = logging.getLogger(__name__)


def recording_enabled() -> bool:
    return os.environ.get("AI_OPERATIONS_RECORD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def classify_llm_error(exc: BaseException | None, *, empty: bool = False) -> str:
    if empty:
        return "empty"
    if exc is None:
        return "unknown"
    if isinstance(exc, CircuitOpenError):
        return "circuit_open"
    if isinstance(exc, TimeoutError):
        return "timeout"
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "401" in msg or "403" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return "auth"
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return "rate_limit"
    if "404" in msg or ("model" in msg and "not found" in msg):
        return "model_not_found"
    return "unknown"


async def record_llm_attempt(
    *,
    task: str,
    provider: str,
    model: str,
    success: bool,
    latency_ms: int,
    retry_index: int,
    context_type: str | None,
    context_id: str | None,
    error_class: str | None = None,
    fallback_from_provider: str | None = None,
    fallback_from_model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    if not recording_enabled():
        return
    db = await get_db()
    try:
        await insert_ai_operation(
            db,
            operation_id=str(uuid.uuid4()),
            request_id=request_id_var.get() or None,
            started_at=utcnow_str(),
            latency_ms=latency_ms,
            feature=task,
            task_class=task,
            provider=provider,
            model=model,
            success=success,
            error_class=error_class,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            fallback_from_provider=fallback_from_provider,
            fallback_from_model=fallback_from_model,
            retry_index=retry_index,
            context_type=context_type,
            context_id=context_id,
        )
        await db.commit()
    except Exception:
        logger.warning("Failed to record ai_operations row", exc_info=True)
    finally:
        await db.close()


class AttemptTimer:
    def __init__(self) -> None:
        self._start = monotonic()

    def elapsed_ms(self) -> int:
        return max(0, int((monotonic() - self._start) * 1000))
