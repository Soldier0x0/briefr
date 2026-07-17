"""Outbound attribution contextvars for metering (Q2) and job wrappers (Q1)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_actor_type: ContextVar[str | None] = ContextVar("outbound_actor_type", default=None)
_actor_id: ContextVar[str | None] = ContextVar("outbound_actor_id", default=None)
_job_id: ContextVar[str | None] = ContextVar("outbound_job_id", default=None)
_run_id: ContextVar[str | None] = ContextVar("outbound_run_id", default=None)
_trigger: ContextVar[str | None] = ContextVar("outbound_trigger", default=None)
_queue_task: ContextVar[str | None] = ContextVar("outbound_queue_task", default=None)


def get_outbound_context() -> dict[str, str | None]:
    return {
        "actor_type": _actor_type.get(),
        "actor_id": _actor_id.get(),
        "job_id": _job_id.get(),
        "run_id": _run_id.get(),
        "trigger": _trigger.get(),
        "queue_task": _queue_task.get(),
    }


@contextmanager
def outbound_context(
    *,
    actor_type: str | None = None,
    actor_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    trigger: str | None = None,
    queue_task: str | None = None,
) -> Iterator[None]:
    """Set attribution fields for the current async task / request scope."""
    tokens = []
    if actor_type is not None:
        tokens.append((_actor_type, _actor_type.set(actor_type)))
    if actor_id is not None:
        tokens.append((_actor_id, _actor_id.set(actor_id)))
    if job_id is not None:
        tokens.append((_job_id, _job_id.set(job_id)))
    if run_id is not None:
        tokens.append((_run_id, _run_id.set(run_id)))
    if trigger is not None:
        tokens.append((_trigger, _trigger.set(trigger)))
    if queue_task is not None:
        tokens.append((_queue_task, _queue_task.set(queue_task)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
