"""Per-job LLM provider session — skip providers that returned empty after failover."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from resilient_client import is_circuit_open, record_source_failure

# Providers marked after an empty response within the active job session.
_job_empty_providers: ContextVar[set[str] | None] = ContextVar(
    "llm_job_empty_providers",
    default=None,
)


@contextmanager
def llm_job_session() -> Iterator[None]:
    """Scope scheduler batch jobs so empty providers are not retried on every CVE."""
    token = _job_empty_providers.set(set())
    try:
        yield
    finally:
        _job_empty_providers.reset(token)


def is_provider_skipped_in_job(provider: str) -> bool:
    """True when this provider returned empty earlier in the current job session."""
    skipped = _job_empty_providers.get()
    return skipped is not None and provider in skipped


def mark_provider_empty_response(provider: str) -> None:
    """Count empty LLM body toward circuit health; skip provider for rest of job."""
    record_source_failure(provider, "empty LLM response content")
    skipped = _job_empty_providers.get()
    if skipped is not None:
        skipped.add(provider)


def provider_circuit_open(provider: str) -> bool:
    """True when the shared resilient-client circuit is open for this provider."""
    return is_circuit_open(provider)
