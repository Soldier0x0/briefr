"""Software catalog autocomplete (Q3) + Tier A stack backfill (Q4)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_db
from db.software_catalog import suggest_software
from db.stack_backfill import (
    count_corpus_hits,
    create_run,
    estimate_eta,
    get_run,
    list_checkpoints,
    products_from_profile,
    stack_backfill_enabled,
)
from dependencies import require_user
from preferences.repo import get_user_stack

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stack", tags=["stack"])


@router.get("/catalog/suggest")
async def catalog_suggest(
    q: str = Query("", min_length=0, max_length=128),
    limit: int = Query(20, ge=1, le=50),
    category: str | None = Query(None, max_length=32),
    payload: dict = Depends(require_user),
):
    """Typeahead for stack products. Requires ≥3 characters; shorter → empty list."""
    _ = payload
    query = (q or "").strip()
    if len(query) < 3:
        return {"ok": True, "query": query, "items": []}
    allowed = {
        "app", "library", "os", "web_server", "firewall", "database", "other"
    }
    cat = (category or "").strip().lower() or None
    if cat and cat not in allowed:
        raise HTTPException(400, f"Invalid category. Allowed: {sorted(allowed)}")
    db = await get_db()
    try:
        items = await suggest_software(db, query=query, limit=limit, category=cat)
    finally:
        await db.close()
    return {"ok": True, "query": query, "items": items}


@router.get("/coverage")
async def stack_coverage(payload: dict = Depends(require_user)):
    """Corpus coverage for the saved stack — gap banner input (Q4)."""
    user_id = int(payload["sub"])
    db = await get_db()
    try:
        stack = await get_user_stack(db, user_id)
        products = products_from_profile(stack.get("profile"), stack.get("stack_terms") or "")
        hits = await count_corpus_hits(db, products)
        shallow = [h for h in hits if h.get("shallow")]
        eta = estimate_eta(shallow or products)
        return {
            "ok": True,
            "enabled": stack_backfill_enabled(),
            "products": hits,
            "shallow_count": len(shallow),
            "needs_backfill": bool(shallow) and stack_backfill_enabled(),
            "eta": eta,
        }
    finally:
        await db.close()


@router.post("/backfill/agree")
async def stack_backfill_agree(payload: dict = Depends(require_user)):
    """Enqueue Tier A historical backfill for shallow stack products."""
    if not stack_backfill_enabled():
        raise HTTPException(403, "STACK_BACKFILL_ENABLED is off")
    user_id = int(payload["sub"])
    db = await get_db()
    try:
        stack = await get_user_stack(db, user_id)
        products = products_from_profile(stack.get("profile"), stack.get("stack_terms") or "")
        if not products:
            raise HTTPException(400, "No stack products to backfill — save My Stack first")
        hits = await count_corpus_hits(db, products)
        targets = [h for h in hits if h.get("shallow")] or products
        eta = estimate_eta(targets)
        run_id = await create_run(db, user_id=user_id, products=targets, eta=eta)
        await db.commit()
    finally:
        await db.close()

    await _kick_backfill(run_id)
    return {
        "ok": True,
        "run_id": run_id,
        "eta": eta,
        "message": "Tier A queued. Deep intel stays on background jobs.",
    }


@router.get("/backfill/{run_id}")
async def stack_backfill_status(run_id: int, payload: dict = Depends(require_user)):
    user_id = int(payload["sub"])
    db = await get_db()
    try:
        run = await get_run(db, run_id, user_id=user_id)
        if not run:
            raise HTTPException(404, "Backfill run not found")
        checkpoints = await list_checkpoints(db, run_id)
    finally:
        await db.close()
    return {"ok": True, "run": run, "checkpoints": checkpoints}


@router.post("/backfill/{run_id}/resume")
async def stack_backfill_resume(run_id: int, payload: dict = Depends(require_user)):
    if not stack_backfill_enabled():
        raise HTTPException(403, "STACK_BACKFILL_ENABLED is off")
    user_id = int(payload["sub"])
    db = await get_db()
    try:
        run = await get_run(db, run_id, user_id=user_id)
        if not run:
            raise HTTPException(404, "Backfill run not found")
        if run.get("status") in ("completed",):
            return {"ok": True, "run_id": run_id, "status": run["status"]}
    finally:
        await db.close()
    await _kick_backfill(run_id)
    return {"ok": True, "run_id": run_id, "message": "Resume kicked"}


async def _kick_backfill(run_id: int) -> None:
    """Defer via Procrastinate when enabled; else in-process task."""
    from jobs.app import is_procrastinate_enabled, open_app

    if is_procrastinate_enabled():
        try:
            from jobs.tasks import stack_backfill_tick

            app = await open_app()
            if app is not None:
                await stack_backfill_tick.defer_async(run_id=run_id)
                return
        except Exception as exc:
            logger.warning("Procrastinate defer failed — falling back: %s", exc)

    from services.stack_backfill_worker import process_stack_backfill_run

    asyncio.create_task(process_stack_backfill_run(run_id))
