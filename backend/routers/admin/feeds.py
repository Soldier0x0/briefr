"""Admin dashboard API — feed circuit breaker and incident refresh.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException, Request

from database import get_db
from dependencies import audit
from feeds.file_identity import (
    EPSS_FILE_IDENTITY_KEY,
    SIGMAHQ_ARCHIVE_IDENTITY_KEY,
    clear_file_identity,
)
from resilient_client import reset_circuit
from task_registry import spawn_background_task

from .helpers import _job_is_disabled
from .router import router

# ── Feed circuit breaker ───────────────────────────────────────────────────


@router.post("/feeds/{source_id}/reset-circuit")
async def reset_feed_circuit(source_id: str, request: Request):
    try:
        reset_circuit(source_id)
    except KeyError:
        raise HTTPException(404, f"Source '{source_id}' not found in health registry")
    await audit(request, f"feed.circuit_reset.{source_id}", source_id)
    return {"ok": True, "source_id": source_id}


@router.post("/feeds/epss/force-resync")
async def force_epss_resync(request: Request):
    """Clear EPSS CSV file identity so the next sync re-applies scores (Q5)."""
    db = await get_db()
    try:
        await clear_file_identity(db, EPSS_FILE_IDENTITY_KEY)
        await db.commit()
    finally:
        await db.close()
    await audit(request, "feed.epss.force_resync", "epss_csv_file_identity")
    return {
        "ok": True,
        "cleared": EPSS_FILE_IDENTITY_KEY,
        "message": "EPSS file identity cleared — next epss_score_sync will re-apply",
    }


@router.post("/feeds/sigmahq/force-resync")
async def force_sigmahq_resync(request: Request):
    """Clear SigmaHQ archive identity and spawn a forced index re-apply (KTD7).

    Unlike EPSS (clear-only), this also starts ``run_sigmahq_index_sync(force=True)``
    so operators do not need a second Scheduler click.
    """
    if _job_is_disabled("sigmahq_index_sync"):
        raise HTTPException(
            400,
            "SigmaHQ index sync is disabled — set SIGMAHQ_INDEX_SYNC_ENABLED=1 in Admin → Config",
        )
    db = await get_db()
    try:
        await clear_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)
        await db.commit()
    finally:
        await db.close()

    from scheduler import run_sigmahq_index_sync

    spawn_background_task(run_sigmahq_index_sync(force=True))
    await audit(request, "feed.sigmahq.force_resync", SIGMAHQ_ARCHIVE_IDENTITY_KEY)
    return {
        "ok": True,
        "cleared": SIGMAHQ_ARCHIVE_IDENTITY_KEY,
        "started": True,
        "message": (
            "SigmaHQ archive identity cleared and index sync started "
            "(force re-apply)"
        ),
    }


@router.post("/incidents/refresh")
async def refresh_incidents_feed(
    request: Request, body: dict, background_tasks: BackgroundTasks
):
    """Refresh one or more incident-feed sources (RSS outlet or ATLAS).

    Body: ``{"sources": ["krebs", "atlas"]}`` — omit or pass ``[]`` for a
    full rebuild (same as the ``incident_feed_refresh`` scheduler job).
    """
    from feeds.case_study_feed import INCIDENT_SOURCE_IDS, refresh_incident_feed_sources

    sources = body.get("sources")
    if sources is not None and not isinstance(sources, list):
        raise HTTPException(400, "sources must be a list of source ids")
    if sources:
        unknown = sorted(set(sources) - INCIDENT_SOURCE_IDS)
        if unknown:
            raise HTTPException(
                400,
                f"Unknown source(s): {unknown}. Valid: {sorted(INCIDENT_SOURCE_IDS)}",
            )

    target = sources if sources else None
    label = ",".join(sorted(target)) if target else "all"

    async def _run() -> None:
        try:
            await refresh_incident_feed_sources(target)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Incident feed refresh failed (%s): %s", label, exc
            )

    background_tasks.add_task(_run)
    await audit(request, "incidents.refresh", label)
    return {
        "ok": True,
        "sources": target or "all",
        "message": f"Incident feed refresh started for {label}",
    }

