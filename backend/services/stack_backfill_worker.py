"""Process Tier A stack backfill runs (Q4).

NVD keyword pages → upsert_cves → EPSS filter apply → KEV flag match.
Never calls OTX / exploits / correlation.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from database import get_db
from db.enrichment import mark_cves_as_kev, update_epss_scores, upsert_kev_batch
from db.stack_backfill import (
    get_run,
    list_checkpoints,
    next_pending_checkpoint,
    update_run,
    upsert_checkpoint,
)
from feeds.epss import fetch_epss_bulk
from feeds.kev import fetch_kev
from feeds.nvd import RESULTS_PER_PAGE, fetch_cves_keyword_page
from jobs.context import outbound_context

logger = logging.getLogger(__name__)


async def process_stack_backfill_run(run_id: int) -> dict:
    """Advance one run until complete, caps hit, or a deferrable error."""
    with outbound_context(
        actor_type="queue",
        queue_task="jobs:stack_backfill",
        trigger="stack_backfill",
        job_id=f"stack_backfill:{run_id}",
    ):
        return await _process(run_id)


async def _process(run_id: int) -> dict:
    started = time.monotonic()
    db = await get_db()
    try:
        run = await get_run(db, run_id)
        if not run:
            return {"ok": False, "error": "not_found"}
        if run.get("status") in ("completed", "partial", "failed"):
            return {"ok": True, "status": run["status"]}

        await update_run(db, run_id, status="running", progress_message="Starting Tier A…")
        await db.commit()

        api_key = os.environ.get("NVD_API_KEY")
        max_cves = int(run.get("max_cves") or 5000)
        max_runtime = int(run.get("max_runtime_seconds") or 3600)
        cves_upserted = int(run.get("cves_upserted") or 0)
        pages_done = int(run.get("pages_done") or 0)
        new_ids: list[str] = []

        while True:
            if time.monotonic() - started > max_runtime:
                await update_run(
                    db,
                    run_id,
                    status="partial",
                    progress_message="Paused — max runtime reached. Resume later.",
                )
                await db.commit()
                return {"ok": True, "status": "partial", "reason": "max_runtime"}

            if cves_upserted >= max_cves:
                await update_run(
                    db,
                    run_id,
                    status="partial",
                    progress_message="Paused — max CVE cap reached. Continue later.",
                    cves_upserted=cves_upserted,
                )
                await db.commit()
                return {"ok": True, "status": "partial", "reason": "max_cves"}

            cp = await next_pending_checkpoint(db, run_id)
            if not cp:
                break

            product = cp["product"]
            start_index = int(cp.get("start_index") or 0)
            await upsert_checkpoint(
                db,
                run_id=run_id,
                product_key=cp["product_key"],
                vendor=cp.get("vendor"),
                product=product,
                version=cp.get("version"),
                status="running",
                start_index=start_index,
                total_results=int(cp.get("total_results") or 0),
                cves_upserted=int(cp.get("cves_upserted") or 0),
            )
            await update_run(
                db,
                run_id,
                progress_message=f"Fetching NVD pages for {product} (start={start_index})…",
            )
            await db.commit()

            cves, total, err = await fetch_cves_keyword_page(
                product,
                start_index=start_index,
                api_key=api_key,
            )
            if err == "rate_limited":
                await upsert_checkpoint(
                    db,
                    run_id=run_id,
                    product_key=cp["product_key"],
                    vendor=cp.get("vendor"),
                    product=product,
                    version=cp.get("version"),
                    status="deferred",
                    start_index=start_index,
                    total_results=int(cp.get("total_results") or 0),
                    cves_upserted=int(cp.get("cves_upserted") or 0),
                    last_error="rate_limited",
                )
                await update_run(
                    db,
                    run_id,
                    status="deferred",
                    progress_message="Rate limited — will resume automatically.",
                )
                await db.commit()
                return {"ok": True, "status": "deferred"}
            if err == "http_5xx":
                await upsert_checkpoint(
                    db,
                    run_id=run_id,
                    product_key=cp["product_key"],
                    vendor=cp.get("vendor"),
                    product=product,
                    version=cp.get("version"),
                    status="on_hold",
                    start_index=start_index,
                    total_results=int(cp.get("total_results") or 0),
                    cves_upserted=int(cp.get("cves_upserted") or 0),
                    last_error="http_5xx",
                )
                await update_run(
                    db,
                    run_id,
                    status="on_hold",
                    progress_message=f"NVD 5xx for {product} — on hold.",
                )
                await db.commit()
                return {"ok": True, "status": "on_hold"}
            if err == "not_found" or (total == 0 and start_index == 0):
                await upsert_checkpoint(
                    db,
                    run_id=run_id,
                    product_key=cp["product_key"],
                    vendor=cp.get("vendor"),
                    product=product,
                    version=cp.get("version"),
                    status="not_found",
                    start_index=0,
                    total_results=0,
                    cves_upserted=0,
                    last_error="not_found",
                )
                pages_done += 1
                await update_run(db, run_id, pages_done=pages_done)
                await db.commit()
                continue

            from db.cve import upsert_cves

            await upsert_cves(db, cves)
            ids = [c["cve_id"] for c in cves if c.get("cve_id")]
            new_ids.extend(ids)
            cves_upserted += len(ids)
            pages_done += 1
            next_index = start_index + RESULTS_PER_PAGE
            done_product = next_index >= total or not cves
            await upsert_checkpoint(
                db,
                run_id=run_id,
                product_key=cp["product_key"],
                vendor=cp.get("vendor"),
                product=product,
                version=cp.get("version"),
                status="done" if done_product else "pending",
                start_index=0 if done_product else next_index,
                total_results=total,
                cves_upserted=int(cp.get("cves_upserted") or 0) + len(ids),
            )
            # Personalized ETA: remaining pages × paced seconds
            remaining_pages = max(0, (total - next_index + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
            cps = await list_checkpoints(db, run_id)
            pending_products = sum(
                1 for c in cps if c.get("status") in ("pending", "running", "deferred", "on_hold")
            )
            paced = 60.0 / 50.0 if api_key else 60.0 / 5.0
            eta_left = int((remaining_pages + pending_products) * paced + 45)
            await update_run(
                db,
                run_id,
                cves_upserted=cves_upserted,
                pages_done=pages_done,
                eta_low_seconds=max(0, int(eta_left * 0.7)),
                eta_high_seconds=int(eta_left * 1.3),
                progress_message=f"Upserted {len(ids)} CVEs for {product} ({cves_upserted} total).",
            )
            await db.commit()

        # EPSS + KEV for newly upserted IDs (best-effort)
        unique_ids = sorted(set(new_ids))
        if unique_ids:
            await update_run(db, run_id, progress_message="Applying EPSS + KEV flags…")
            await db.commit()
            try:
                scores = await fetch_epss_bulk(set(unique_ids))
                if scores:
                    await update_epss_scores(db, scores)
            except Exception as exc:
                logger.warning("EPSS apply after backfill failed: %s", exc)
            try:
                kev_entries = await fetch_kev()
                await upsert_kev_batch(db, kev_entries)
                kev_ids = [e["cveID"] for e in kev_entries if e.get("cveID")]
                await mark_cves_as_kev(db, kev_ids)
            except Exception as exc:
                logger.warning("KEV apply after backfill failed: %s", exc)
            await db.commit()

        done_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        await update_run(
            db,
            run_id,
            status="completed",
            progress_message=(
                f"Tier A complete — {cves_upserted} CVEs. "
                "Deep intel (OTX/exploits/correlation) continues on background jobs."
            ),
            cves_upserted=cves_upserted,
            pages_done=pages_done,
            completed_at=done_at,
        )
        await db.commit()
        return {"ok": True, "status": "completed", "cves_upserted": cves_upserted}
    except Exception as exc:
        logger.exception("stack backfill run %s failed", run_id)
        try:
            await update_run(
                db,
                run_id,
                status="failed",
                error_message=str(exc)[:500],
                progress_message="Tier A failed — see error.",
            )
            await db.commit()
        except Exception:
            pass
        return {"ok": False, "error": str(exc)[:200]}
    finally:
        await db.close()
