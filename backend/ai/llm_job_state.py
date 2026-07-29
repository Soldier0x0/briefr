"""Scheduler-visible LLM job failover state (Phase E2b)."""

from __future__ import annotations

from typing import Any

_LLM_JOBS = frozenset({"detection_context_llm", "llm_product_extraction"})

_job_llm_state: dict[str, dict[str, Any]] = {}
_job_lock_started_at: dict[str, float] = {}


def is_llm_job(job_id: str) -> bool:
    return job_id in _LLM_JOBS


def record_lock_started(job_id: str, started_at: float) -> None:
    _job_lock_started_at[job_id] = started_at


def record_lock_released(job_id: str) -> None:
    _job_lock_started_at.pop(job_id, None)
    clear_job_llm_state(job_id)


def lock_started_at(job_id: str) -> float | None:
    return _job_lock_started_at.get(job_id)


def update_job_llm_provider(job_id: str, provider: str) -> None:
    if not provider:
        return
    state = _job_llm_state.setdefault(
        job_id,
        {"current_provider": "", "providers_attempted": []},
    )
    state["current_provider"] = provider
    attempted: list[str] = state.setdefault("providers_attempted", [])
    if provider not in attempted:
        attempted.append(provider)


def get_job_llm_state(job_id: str) -> dict[str, Any] | None:
    state = _job_llm_state.get(job_id)
    if not state:
        return None
    return {
        "current_provider": state.get("current_provider") or "",
        "providers_attempted": list(state.get("providers_attempted") or []),
    }


def clear_job_llm_state(job_id: str) -> None:
    _job_llm_state.pop(job_id, None)
