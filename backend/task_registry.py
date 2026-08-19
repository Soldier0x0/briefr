"""Fire-and-forget asyncio task registry with bounded shutdown drain (PR-R1).

The event loop only holds weak references to tasks, and until PR-R1 each
spawn site kept its own strong-reference set that nothing awaited at
shutdown (audit REST-002/REST-012): an ingest or snapshot build could be
killed mid-write when uvicorn stopped. All fire-and-forget spawns register
here so the lifespan shutdown can wait — bounded, never indefinitely — for
them to finish.
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def _on_task_done(task: asyncio.Task) -> None:
    """Drop the strong ref and retrieve exceptions so asyncio does not warn."""
    _tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "Background task %s failed: %s",
            task.get_name(),
            exc,
            exc_info=exc,
        )


def shutdown_drain_timeout_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get("SHUTDOWN_DRAIN_TIMEOUT_SECONDS", "10")))
    except ValueError:
        return 10.0


def register_background_task(task: asyncio.Task) -> asyncio.Task:
    """Track a fire-and-forget task (strong ref + shutdown drain)."""
    _tasks.add(task)
    task.add_done_callback(_on_task_done)
    return task


def spawn_background_task(coro) -> asyncio.Task:
    return register_background_task(asyncio.create_task(coro))


def pending_background_tasks() -> int:
    return sum(1 for t in _tasks if not t.done())


async def drain_background_tasks(timeout: float | None = None) -> int:
    """Wait (bounded) for registered tasks to finish. Returns tasks still
    running when the timeout expired — 0 means a clean drain."""
    if timeout is None:
        timeout = shutdown_drain_timeout_seconds()
    pending = {t for t in _tasks if not t.done()}
    if not pending:
        return 0
    logger.info(
        "Shutdown: waiting up to %.1fs for %d background task(s)", timeout, len(pending)
    )
    _, still_pending = await asyncio.wait(pending, timeout=timeout)
    for task in still_pending:
        name = task.get_name() if hasattr(task, "get_name") else repr(task)
        logger.warning("Background task still running at shutdown: %s", name)
    return len(still_pending)
