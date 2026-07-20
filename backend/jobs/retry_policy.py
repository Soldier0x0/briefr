"""Bounded retry policy for durable Procrastinate tasks."""

from __future__ import annotations

RETRY_DELAYS_SECONDS = (180, 240, 300)


def _is_timeout_like(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    return "command timeout" in str(exc).lower()


def is_retryable_job_error(exc: BaseException) -> bool:
    """Return True when *exc* (or its cause chain) is a transient timeout."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _is_timeout_like(current):
            return True
        current = current.__cause__
    return False


def next_retry_delay_seconds(attempt: int) -> int | None:
    """Return delay seconds for 1-based *attempt*, or None when retries are exhausted."""
    if attempt < 1:
        return None
    index = attempt - 1
    if index >= len(RETRY_DELAYS_SECONDS):
        return None
    return RETRY_DELAYS_SECONDS[index]
