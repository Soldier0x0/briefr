import asyncio
import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import (
    get_db,
    get_all_cve_ids,
    get_cve_count,
    mark_cves_as_kev,
    update_epss_scores,
    upsert_cve,
    upsert_kev,
)
from feeds.nvd import fetch_recent_cves, fetch_cve_by_id
from feeds.kev import fetch_kev
from feeds.epss import fetch_epss

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def run_daily_refresh() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("Daily CVE refresh started at %s", start_time.isoformat())

    nvd_api_key = os.environ.get("NVD_API_KEY")
    max_cves = int(os.environ.get("MAX_CVES_PER_FETCH", "2000"))

    new_or_updated = 0
    kev_count = 0
    epss_updated = 0

    try:
        logger.info("Step 1/3: Fetching CVEs from NVD")
        cves = await fetch_recent_cves(api_key=nvd_api_key, days_back=7)
        cves = cves[:max_cves]

        db = await get_db()
        try:
            for cve in cves:
                await upsert_cve(db, cve)
                new_or_updated += 1
            await db.commit()
        finally:
            await db.close()

        logger.info("Step 1/3 complete: %d CVEs upserted", new_or_updated)

    except Exception as exc:
        logger.error("Step 1/3 failed (NVD fetch): %s", exc)

    kev_entries: list = []
    try:
        logger.info("Step 2/3: Fetching CISA KEV catalog")
        kev_entries = await fetch_kev()

        db = await get_db()
        try:
            kev_ids = []
            for entry in kev_entries:
                await upsert_kev(db, entry)
                cve_id = entry.get("cveID", "")
                if cve_id:
                    kev_ids.append(cve_id)
                    kev_count += 1

            await mark_cves_as_kev(db, kev_ids)
            await db.commit()
        finally:
            await db.close()

        logger.info("Step 2/3 complete: %d KEV entries processed", kev_count)

        db = await get_db()
        try:
            existing_ids = set(await get_all_cve_ids(db))
        finally:
            await db.close()

        kev_cve_ids = [e.get("cveID", "") for e in kev_entries if e.get("cveID")]
        missing_kev = [cve_id for cve_id in kev_cve_ids if cve_id not in existing_ids]

        if missing_kev:
            logger.info(
                "Step 2.5: Cross-fetching %d KEV CVEs missing from cves table",
                len(missing_kev),
            )
            kev_cross_fetched = 0
            for kev_cve_id in missing_kev:
                try:
                    cve_data = await fetch_cve_by_id(kev_cve_id, nvd_api_key)
                    if cve_data:
                        cve_data["is_kev"] = True
                        db = await get_db()
                        try:
                            await upsert_cve(db, cve_data)
                            await db.commit()
                            kev_cross_fetched += 1
                        finally:
                            await db.close()
                except Exception as exc:
                    logger.error("KEV cross-fetch failed for %s: %s", kev_cve_id, exc)
                await asyncio.sleep(1)
            logger.info("Step 2.5 complete: %d KEV CVEs newly fetched from NVD", kev_cross_fetched)
        else:
            logger.info("Step 2.5: All KEV CVEs already present in cves table")

    except Exception as exc:
        logger.error("Step 2/3 failed (KEV fetch): %s", exc)

    try:
        logger.info("Step 3/3: Fetching EPSS scores")

        db = await get_db()
        try:
            all_cve_ids = await get_all_cve_ids(db)
        finally:
            await db.close()

        if all_cve_ids:
            scores = await fetch_epss(all_cve_ids)
            epss_updated = len(scores)

            db = await get_db()
            try:
                await update_epss_scores(db, scores)
                await db.commit()
            finally:
                await db.close()

        logger.info("Step 3/3 complete: EPSS scores updated for %d CVEs", epss_updated)

    except Exception as exc:
        logger.error("Step 3/3 failed (EPSS fetch): %s", exc)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    logger.info(
        "Daily CVE refresh complete. Duration: %.1fs. New/updated: %d, KEV: %d, EPSS: %d",
        duration,
        new_or_updated,
        kev_count,
        epss_updated,
    )


async def maybe_run_on_startup() -> None:
    db = await get_db()
    try:
        count = await get_cve_count(db)
    finally:
        await db.close()

    if count < 10:
        logger.info("CVE table has %d rows (< 10). Running initial fetch on startup.", count)
        asyncio.create_task(run_daily_refresh())
    else:
        logger.info("CVE table has %d rows. Skipping startup fetch.", count)


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler

    refresh_hour = int(os.environ.get("CACHE_REFRESH_HOUR", "6"))
    refresh_minute = int(os.environ.get("CACHE_REFRESH_MINUTE", "0"))

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_daily_refresh,
        trigger=CronTrigger(hour=refresh_hour, minute=refresh_minute, timezone="Asia/Kolkata"),
        id="daily_cve_refresh",
        name="Daily CVE Refresh",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started. Daily refresh scheduled at %02d:%02d IST.",
        refresh_hour,
        refresh_minute,
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    _scheduler = None
