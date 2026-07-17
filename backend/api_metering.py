"""Fire-and-forget metering from resilient_client (Q2)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def is_api_call_events_enabled() -> bool:
    raw = os.environ.get("API_CALL_EVENTS_ENABLED", "1").strip().lower()
    # Default on once table exists; operators can set 0. Metering never fails callers.
    return raw not in ("0", "false", "no", "off")


async def record_outbound_attempt(
    *,
    source: str,
    method: str,
    url: str,
    status_code: int | None,
    ok: bool,
    latency_ms: int,
    error_class: str | None = None,
) -> None:
    if not is_api_call_events_enabled():
        return
    try:
        from jobs.context import get_outbound_context
        from structured_logging import job_id_var, request_id_var, run_id_var

        ctx = get_outbound_context()
        actor_type = ctx.get("actor_type")
        job_id = ctx.get("job_id") or job_id_var.get()
        run_id = ctx.get("run_id") or run_id_var.get()
        request_id = request_id_var.get()
        if actor_type is None and job_id:
            actor_type = "job"
        if actor_type is None and request_id:
            actor_type = "user"

        from database import get_db
        from db.api_metering import insert_api_call_event, touch_api_usage_last_called
        from tracking import record_api_call

        db = await get_db()
        try:
            await insert_api_call_event(
                db,
                source=source,
                method=method,
                url=url,
                status_code=status_code,
                ok=ok,
                latency_ms=latency_ms,
                actor_type=actor_type,
                actor_id=ctx.get("actor_id"),
                job_id=job_id,
                run_id=run_id,
                queue_task=ctx.get("queue_task"),
                request_id=request_id,
                error_class=error_class,
                pacing_key=source,
            )
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await touch_api_usage_last_called(db, service=source, date_utc=day)
            await db.commit()
        finally:
            await db.close()

        # Keep rollup counters in sync (same choke point as events).
        await record_api_call(source, 1)
    except Exception as exc:
        logger.warning("api metering failed (ignored): %s", exc)
