import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import (
    backfill_display_fields,
    backfill_has_poc,
    enrich_kev_summaries,
    get_all_cve_ids,
    get_cve_count,
    get_db,
    get_nvd_sync_watermark,
    mark_cves_as_kev,
    resolve_nvd_watermark,
    set_nvd_sync_watermark,
    snapshot_epss_scores,
    strip_auto_generated_summaries,
    update_epss_scores,
    upsert_cve,
    upsert_cves,
    upsert_kev,
)
from feeds.nvd import fetch_cve_by_id, fetch_nvd_cve_updates
from feeds.kev import fetch_kev
from feeds.epss import fetch_epss
from feeds.atlas import refresh_atlas_data
from feeds.mitre import refresh_mitre_data

logger = logging.getLogger(__name__)

SCHEDULER_REFRESH_TZ = "Asia/Kolkata"

_scheduler: AsyncIOScheduler | None = None
_nvd_lock = asyncio.Lock()
_kev_lock = asyncio.Lock()
_epss_lock = asyncio.Lock()
_mitre_refresh_lock = asyncio.Lock()


def get_scheduler_timezone() -> str:
    return os.environ.get("SCHEDULER_TIMEZONE", SCHEDULER_REFRESH_TZ)


def get_ingest_intervals() -> dict:
    return {
        "nvd_hours": int(os.environ.get("NVD_SYNC_INTERVAL_HOURS", "1")),
        "kev_minutes": int(os.environ.get("KEV_SYNC_INTERVAL_MINUTES", "15")),
        "epss_hours": int(os.environ.get("EPSS_SYNC_INTERVAL_HOURS", "6")),
        "timezone": get_scheduler_timezone(),
    }


def get_refresh_schedule() -> dict:
    """Ingest cadence + weekly MITRE window (for /api/health UI)."""
    intervals = get_ingest_intervals()
    mitre_hour = int(os.environ.get("CACHE_REFRESH_HOUR", "6"))
    mitre_minute = int(os.environ.get("MITRE_REFRESH_MINUTE", "30"))
    return {
        "timezone": intervals["timezone"],
        "nvd_interval_hours": intervals["nvd_hours"],
        "kev_interval_minutes": intervals["kev_minutes"],
        "epss_interval_hours": intervals["epss_hours"],
        "mitre_weekly_hour": mitre_hour,
        "mitre_weekly_minute": mitre_minute,
        # Legacy keys (hour/minute were shown as misleading "daily" refresh)
        "hour": mitre_hour,
        "minute": mitre_minute,
    }


def _next_interval_fire_utc(hours: int = 0, minutes: int = 0) -> datetime:
    now = datetime.now(timezone.utc)
    delta = timedelta(hours=hours, minutes=minutes)
    if delta.total_seconds() <= 0:
        delta = timedelta(hours=1)
    return now + delta


def get_next_scheduled_refresh_utc() -> datetime:
    """Next NVD incremental sync from APScheduler, or interval fallback."""
    global _scheduler
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("nvd_incremental_sync")
        if job and job.next_run_time:
            return job.next_run_time.astimezone(timezone.utc)
    return _next_interval_fire_utc(hours=get_ingest_intervals()["nvd_hours"])


def ingest_in_progress() -> bool:
    return _nvd_lock.locked() or _kev_lock.locked() or _epss_lock.locked()


def refresh_in_progress() -> bool:
    """Alias for API compatibility."""
    return ingest_in_progress()


def get_ingest_status() -> dict:
    return {
        "nvd_in_progress": _nvd_lock.locked(),
        "kev_in_progress": _kev_lock.locked(),
        "epss_in_progress": _epss_lock.locked(),
        "mitre_in_progress": _mitre_refresh_lock.locked(),
        "any_in_progress": ingest_in_progress(),
        "intervals": get_ingest_intervals(),
    }


async def run_nvd_incremental_sync() -> bool:
    if _nvd_lock.locked():
        logger.warning("NVD sync already in progress — skipping")
        return False

    async with _nvd_lock:
        await _run_nvd_incremental_sync()
    return True


async def _run_nvd_incremental_sync() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("NVD incremental sync started at %s", start_time.isoformat())

    nvd_api_key = os.environ.get("NVD_API_KEY")
    max_cves = int(os.environ.get("MAX_CVES_PER_FETCH", "2000"))
    days_back = int(os.environ.get("NVD_DAYS_BACK", "14"))
    overlap_minutes = int(os.environ.get("NVD_SYNC_OVERLAP_MINUTES", "15"))

    new_or_updated = 0

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
            await upsert_cves(db, cves)
            new_or_updated = len(cves)
            await set_nvd_sync_watermark(db, new_watermark)
            updated_ids = [
                (cve.get("cve_id") or "").upper()
                for cve in cves
                if cve.get("cve_id")
            ]
            if updated_ids:
                stripped = await strip_auto_generated_summaries(db, updated_ids)
                filled = await backfill_display_fields(db, updated_ids)
                poc_marked = await backfill_has_poc(db, updated_ids)
            else:
                stripped = filled = poc_marked = 0
            await db.commit()
            logger.info(
                "NVD post-process: stripped %d summaries, %d display fields, %d PoC flags",
                stripped,
                filled,
                poc_marked,
            )
        finally:
            await db.close()

        mode = "incremental (lastMod)" if used_incremental else "full (published window)"
        logger.info("NVD sync complete (%s): %d CVEs upserted", mode, new_or_updated)

    except Exception as exc:
        logger.error("NVD incremental sync failed: %s", exc)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("NVD incremental sync finished in %.1fs", duration)


async def run_kev_sync() -> bool:
    if _kev_lock.locked():
        logger.warning("KEV sync already in progress — skipping")
        return False

    async with _kev_lock:
        await _run_kev_sync()
    return True


async def _run_kev_sync() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("KEV metadata sync started at %s", start_time.isoformat())

    nvd_api_key = os.environ.get("NVD_API_KEY")
    kev_count = 0

    try:
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
            kev_summaries = await enrich_kev_summaries(db)
            await db.commit()
            if kev_summaries:
                logger.info("Enriched %d KEV summaries from CISA descriptions", kev_summaries)
        finally:
            await db.close()

        logger.info("KEV sync complete: %d catalog entries processed", kev_count)

        if os.environ.get("KEV_CROSS_FETCH_NVD", "1").strip().lower() in ("1", "true", "yes"):
            await _cross_fetch_missing_kev_cves(kev_entries, nvd_api_key)

    except Exception as exc:
        logger.error("KEV sync failed: %s", exc)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("KEV metadata sync finished in %.1fs", duration)


async def _cross_fetch_missing_kev_cves(kev_entries: list[dict], nvd_api_key: str | None) -> None:
    try:
        db = await get_db()
        try:
            existing_ids = set(await get_all_cve_ids(db))
            missing_kev = [
                e.get("cveID", "")
                for e in kev_entries
                if e.get("cveID") and e.get("cveID") not in existing_ids
            ]
            if not missing_kev:
                return

            logger.info("KEV cross-fetch: %d CVEs missing from cves table", len(missing_kev))
            kev_short_map = {
                e.get("cveID", ""): e.get("shortDescription", "") for e in kev_entries
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
                        await upsert_cve(db, cve_data)
                        kev_cross_fetched += 1
                except Exception as exc:
                    logger.error("KEV cross-fetch failed for %s: %s", kev_cve_id, exc)
                await asyncio.sleep(1)
            if kev_cross_fetched:
                await db.commit()
            logger.info("KEV cross-fetch complete: %d CVEs inserted", kev_cross_fetched)
        finally:
            await db.close()
    except Exception as exc:
        logger.error("KEV cross-fetch step failed: %s", exc)


async def run_epss_sync() -> bool:
    if _epss_lock.locked():
        logger.warning("EPSS sync already in progress — skipping")
        return False

    async with _epss_lock:
        await _run_epss_sync()
    return True


async def _run_epss_sync() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("EPSS score sync started at %s", start_time.isoformat())

    epss_updated = 0

    try:
        db = await get_db()
        try:
            all_cve_ids = await get_all_cve_ids(db)
        finally:
            await db.close()

        if not all_cve_ids:
            logger.info("EPSS sync skipped: no CVEs in database")
            return

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

        logger.info("EPSS sync complete: %d scores processed", epss_updated)

    except Exception as exc:
        logger.error("EPSS sync failed: %s", exc)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("EPSS score sync finished in %.1fs", duration)


async def run_full_ingest_sync() -> bool:
    """Run NVD, KEV, and EPSS pipelines sequentially (manual / bootstrap)."""
    if ingest_in_progress():
        logger.warning("Ingest already in progress — ignoring full sync request")
        return False

    await run_nvd_incremental_sync()
    await run_kev_sync()
    await run_epss_sync()
    return True


async def run_daily_refresh() -> bool:
    """Backward-compatible entry point for POST /api/refresh."""
    return await run_full_ingest_sync()


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
                await db.commit()
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
    from database import enrich_kev_summaries, strip_auto_generated_summaries

    count = 0
    db = await get_db()
    try:
        count = await get_cve_count(db)
        if count >= 10:
            stripped = await strip_auto_generated_summaries(db)
            await enrich_kev_summaries(db)
            await db.commit()
            if stripped:
                logger.info(
                    "Startup: cleared %d auto-generated plain summaries", stripped
                )
    finally:
        await db.close()

    if count < 10:
        logger.info("CVE table has %d rows (< 10). Running full ingest on startup.", count)
        asyncio.create_task(run_full_ingest_sync())
    else:
        logger.info(
            "CVE table has %d rows. Incremental schedulers will maintain freshness.",
            count,
        )

    await maybe_run_mitre_on_startup()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler

    intervals = get_ingest_intervals()
    tz_name = intervals["timezone"]
    sched_tz = ZoneInfo(tz_name)

    scheduler = AsyncIOScheduler(timezone=sched_tz)

    scheduler.add_job(
        run_nvd_incremental_sync,
        trigger=IntervalTrigger(hours=intervals["nvd_hours"], timezone=sched_tz),
        id="nvd_incremental_sync",
        name="NVD Incremental Sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_kev_sync,
        trigger=IntervalTrigger(minutes=intervals["kev_minutes"], timezone=sched_tz),
        id="kev_metadata_sync",
        name="KEV Metadata Sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_epss_sync,
        trigger=IntervalTrigger(hours=intervals["epss_hours"], timezone=sched_tz),
        id="epss_score_sync",
        name="EPSS Score Sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    refresh_hour = int(os.environ.get("CACHE_REFRESH_HOUR", "6"))
    mitre_minute = int(os.environ.get("MITRE_REFRESH_MINUTE", "30"))
    scheduler.add_job(
        run_weekly_mitre_refresh,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=refresh_hour,
            minute=mitre_minute,
            timezone=sched_tz,
        ),
        id="weekly_mitre_refresh",
        name="Weekly MITRE ATT&CK + ATLAS Refresh",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started (tz=%s). NVD every %dh; KEV every %dm; EPSS every %dh; "
        "MITRE+ATLAS weekly Sunday %02d:%02d.",
        tz_name,
        intervals["nvd_hours"],
        intervals["kev_minutes"],
        intervals["epss_hours"],
        refresh_hour,
        mitre_minute,
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    _scheduler = None
