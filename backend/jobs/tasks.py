"""Procrastinate task definitions (Blueprint — bound at App creation)."""

from __future__ import annotations

import logging

import procrastinate
from procrastinate.exceptions import AlreadyEnqueued

from jobs.context import outbound_context
from jobs.retry_policy import is_retryable_job_error, next_retry_delay_seconds
from ml.product_extraction import run_llm_product_extraction
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


@blueprint.task(name="llm_product_extraction", queue="briefr")
async def llm_product_extraction_tick(*, trigger: str = "scheduler", attempts: int = 1) -> dict:
    """Run LLM product extraction from the durable queue (Wave 2)."""
    with outbound_context(
        actor_type="queue",
        queue_task="jobs:llm_product_extraction",
        trigger=trigger,
    ):
        try:
            return await run_llm_product_extraction()
        except Exception as exc:
            delay = (
                next_retry_delay_seconds(attempts)
                if is_retryable_job_error(exc)
                else None
            )
            if delay is None:
                raise
            try:
                # Procrastinate's queueing_lock unique index applies only to `todo`
                # jobs, so the current `doing` job does not block self-defer.
                await llm_product_extraction_tick.configure(
                    queueing_lock="llm_product_extraction",
                    schedule_in={"seconds": delay},
                ).defer_async(trigger=trigger, attempts=attempts + 1)
            except AlreadyEnqueued:
                logger.info(
                    "LLM product extraction retry already queued — skipping duplicate"
                )
            return {
                "ok": False,
                "retry_scheduled": True,
                "attempts": attempts,
                "retry_in_seconds": delay,
            }
