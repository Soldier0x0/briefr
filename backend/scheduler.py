import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import (
    backfill_display_fields,
    backfill_has_poc,
    enrich_kev_summaries,
    get_db,
    get_all_cve_ids,
    get_cve_count,
    get_nvd_sync_watermark,
    mark_cves_as_kev,
    resolve_nvd_watermark,
    set_nvd_sync_watermark,
    snapshot_epss_scores,
    update_epss_scores,
    upsert_cve,
    upsert_kev,
)
from feeds.nvd import fetch_cve_by_id, fetch_nvd_cve_updates
from feeds.kev import fetch_kev
from feeds.epss import fetch_epss
from feeds.atlas import refresh_atlas_data
from feeds.mitre import refresh_mitre_data

logger = logging.getLogger(__name__)


SCHEDULER_REFRESH_TZ = "Asia/Kolkata"


def get_refresh_schedule() -> dict:
    return {
        "hour": int(os.environ.get("CACHE_REFRESH_HOUR", "6")),
        "minute": int(os.environ.get("CACHE_REFRESH_MINUTE", "0")),
        "timezone": SCHEDULER_REFRESH_TZ,
    }


def get_next_scheduled_refresh_utc() -> datetime:
    sched = get_refresh_schedule()
    tz = ZoneInfo(sched["timezone"])
    now_local = datetime.now(tz)
    candidate = now_local.replace(
        hour=sched["hour"], minute=sched["minute"], second=0, microsecond=0,
    )
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


_scheduler: AsyncIOScheduler | None = None
_refresh_lock = asyncio.Lock()
_mitre_refresh_lock = asyncio.Lock()


def refresh_in_progress() -> bool:
    return _refresh_lock.locked()


async def run_daily_refresh() -> bool:
    if _refresh_lock.locked():
        logger.warning("Refresh already in progress — ignoring duplicate request")
        return False

    async with _refresh_lock:
        await _run_daily_refresh()
    return True


async def _run_daily_refresh() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("Daily CVE refresh started at %s", start_time.isoformat())

    nvd_api_key = os.environ.get("NVD_API_KEY")
    max_cves = int(os.environ.get("MAX_CVES_PER_FETCH", "2000"))
    days_back = int(os.environ.get("NVD_DAYS_BACK", "14"))
    overlap_minutes = int(os.environ.get("NVD_SYNC_OVERLAP_MINUTES", "15"))

    new_or_updated = 0
    kev_count = 0
    epss_updated = 0

    try:
        db = await get_db()
        try:
            had_watermark = await get_nvd_sync_watermark(db) is not None
            watermark = await resolve_nvd_watermark(db)
            if watermark and not had_watermark:
                logger.info(
                    "Seeded NVD incremental watermark from existing CVE data: %s",
                    watermark,
                )
                await db.commit()
        finally:
            await db.close()

        logger.info("Step 1/3: Fetching CVEs from NVD")
        cves, mod_end_iso, used_incremental = await fetch_nvd_cve_updates(
            nvd_api_key,
            watermark=watermark,
            days_back=days_back,
            overlap_minutes=overlap_minutes,
        )
        cves.sort(key=lambda x: x.get("modified") or "")

        capped = len(cves) > max_cves
        if capped:
            logger.warning(
                "NVD returned %d CVEs; capping upsert at MAX_CVES_PER_FETCH=%d",
                len(cves),
                max_cves,
            )
            cves = cves[:max_cves]

        if capped and cves:
            last_modified = cves[-1].get("modified")
            new_watermark = last_modified if last_modified else mod_end_iso
        else:
            new_watermark = mod_end_iso

        db = await get_db()
        try:
            for cve in cves:
                await upsert_cve(db, cve)
                new_or_updated += 1
            await set_nvd_sync_watermark(db, new_watermark)
            await db.commit()
        finally:
            await db.close()

        mode = "incremental (lastMod)" if used_incremental else "full (published window)"
        logger.info("Step 1/3 complete (%s): %d CVEs upserted", mode, new_or_updated)

    except Exception as exc:
        logger.error("Step 1/3 failed (NVD fetch): %s", exc)

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
            kev_summaries = await enrich_kev_summaries(db)
            await db.commit()
            if kev_summaries:
                logger.info("Enriched %d KEV summaries from CISA descriptions", kev_summaries)
        finally:
            await db.close()

        # Step 2.5: Cross-fetch KEV CVEs not yet in cves table
        try:
            db = await get_db()
            try:
                existing_ids = set(await get_all_cve_ids(db))
            finally:
                await db.close()

            missing_kev = [
                e.get("cveID", "") for e in kev_entries
                if e.get("cveID") and e.get("cveID") not in existing_ids
            ]

            if missing_kev:
                logger.info("Step 2.5: Cross-fetching %d KEV CVEs missing from cves table", len(missing_kev))
                kev_short_map = {
                    e.get("cveID", ""): e.get("shortDescription", "")
                    for e in kev_entries
                }
                kev_cross_fetched = 0
                for kev_cve_id in missing_kev:
                    try:
                        cve_data = await fetch_cve_by_id(kev_cve_id, nvd_api_key)
                        if cve_data:
                            cve_data["is_kev"] = True
                            kev_short = kev_short_map.get(kev_cve_id, "")
                            if kev_short:
                                cve_data["summary"] = kev_short
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
                logger.info("Step 2.5 complete: %d KEV CVEs newly inserted", kev_cross_fetched)
        except Exception as exc:
            logger.error("Step 2.5 failed (KEV cross-fetch): %s", exc)

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
                snapshotted = await snapshot_epss_scores(db)
                await update_epss_scores(db, scores)
                await db.commit()
                if snapshotted:
                    logger.info("EPSS history snapshot: %d CVE scores saved", snapshotted)
            finally:
                await db.close()

        logger.info("Step 3/3 complete: EPSS scores updated for %d CVEs", epss_updated)

    except Exception as exc:
        logger.error("Step 3/3 failed (EPSS fetch): %s", exc)

    try:
        logger.info("Step 4/4: Backfilling summaries and MITRE mappings")
        db = await get_db()
        try:
            filled = await backfill_display_fields(db)
            poc_marked = await backfill_has_poc(db)
            await enrich_kev_summaries(db)
            await db.commit()
            logger.info(
                "Step 4/4 complete: enriched %d display fields, %d PoC flags set",
                filled,
                poc_marked,
            )
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Step 4/4 failed (display enrichment): %s", exc)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    logger.info(
        "Daily CVE refresh complete. Duration: %.1fs. New/updated: %d, KEV: %d, EPSS: %d",
        duration,
        new_or_updated,
        kev_count,
        epss_updated,
    )


async def run_weekly_mitre_refresh() -> bool:
    if _mitre_refresh_lock.locked():
        logger.warning("MITRE refresh already in progress — skipping")
        return False

    async with _mitre_refresh_lock:
        start = datetime.now(timezone.utc)
        logger.info("Weekly MITRE ATT&CK + ATLAS refresh started at %s", start.isoformat())
        ok = True
        try:
            db = await get_db()
            try:
                stats = await refresh_mitre_data(db)
                atlas_stats = await refresh_atlas_data(db)
            finally:
                await db.close()
            logger.info(
                "MITRE refresh complete: %d techniques, %d CVE links (from %d source CVEs)",
                stats["techniques"],
                stats["cve_links"],
                stats["cve_mappings_source"],
            )
            logger.info(
                "ATLAS refresh complete: %d techniques, %d case studies",
                atlas_stats["techniques"],
                atlas_stats["case_studies"],
            )
        except Exception as exc:
            logger.error("Weekly MITRE/ATLAS refresh failed: %s", exc)
            ok = False
        return ok


async def maybe_run_mitre_on_startup() -> None:
    from database import get_atlas_technique_count, get_mitre_technique_count

    db = await get_db()
    try:
        mitre_count = await get_mitre_technique_count(db)
        atlas_count = await get_atlas_technique_count(db)
    finally:
        await db.close()

    if mitre_count < 10 or atlas_count < 10:
        logger.info(
            "MITRE/ATLAS tables sparse (mitre=%d, atlas=%d) — running initial refresh",
            mitre_count,
            atlas_count,
        )
        asyncio.create_task(run_weekly_mitre_refresh())
    else:
        logger.info("MITRE techniques loaded (%d rows), ATLAS (%d rows)", mitre_count, atlas_count)


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

    await maybe_run_mitre_on_startup()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler

    sched = get_refresh_schedule()
    refresh_hour = sched["hour"]
    refresh_minute = sched["minute"]

    scheduler = AsyncIOScheduler(timezone=SCHEDULER_REFRESH_TZ)
    scheduler.add_job(
        run_daily_refresh,
        trigger=CronTrigger(hour=refresh_hour, minute=refresh_minute, timezone=SCHEDULER_REFRESH_TZ),
        id="daily_cve_refresh",
        name="Daily CVE Refresh",
        replace_existing=True,
    )
    mitre_minute = int(os.environ.get("MITRE_REFRESH_MINUTE", "30"))
    scheduler.add_job(
        run_weekly_mitre_refresh,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=refresh_hour,
            minute=mitre_minute,
            timezone=SCHEDULER_REFRESH_TZ,
        ),
        id="weekly_mitre_refresh",
        name="Weekly MITRE ATT&CK + ATLAS Refresh",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started. Daily CVE refresh at %02d:%02d IST; MITRE+ATLAS refresh weekly (Sunday).",
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
