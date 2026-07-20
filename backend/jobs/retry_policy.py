"""Bounded retry policy for durable Procrastinate tasks."""

from __future__ import annotations

RETRY_DELAYS_SECONDS = (180, 240, 300)


def _is_timeout_like(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    message = str(exc).lower()
    return "timeout" in message or "timed out" in message


def is_retryable_job_error(exc: BaseException) -> bool:
    """Return True when *exc* (or its chained exceptions) is a transient timeout."""
    pending: list[BaseException | None] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if _is_timeout_like(current):
            return True
        pending.append(current.__cause__)
        pending.append(current.__context__)
    return False


def next_retry_delay_seconds(attempt: int) -> int | None:
    """Return delay seconds for 1-based *attempt*, or None when retries are exhausted."""
    if attempt < 1:
        return None
    index = attempt - 1
    if index >= len(RETRY_DELAYS_SECONDS):
        return None
    return RETRY_DELAYS_SECONDS[index]
