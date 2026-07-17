"""Procrastinate task definitions (Blueprint — bound at App creation)."""

from __future__ import annotations

import logging

import procrastinate

from jobs.context import outbound_context
from services.stack_backfill_worker import process_stack_backfill_run

logger = logging.getLogger(__name__)

blueprint = procrastinate.Blueprint()


@blueprint.task(name="health_ping", queue="briefr")
async def health_ping(*, note: str = "ok") -> dict:
    """No-op health task — proves defer → worker → success across restarts.
    Registered as ``jobs:health_ping`` via App.add_tasks_from(namespace='jobs').
    """
    with outbound_context(actor_type="queue", queue_task="jobs:health_ping", trigger="health"):
        logger.info("procrastinate health_ping note=%s", note)
        return {"ok": True, "note": note}


@blueprint.task(name="stack_backfill", queue="briefr")
async def stack_backfill_tick(*, run_id: int) -> dict:
    """Advance one Tier A stack backfill run (Q4)."""
    return await process_stack_backfill_run(int(run_id))
