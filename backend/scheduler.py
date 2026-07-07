import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scheduler_locks import any_locked, get_lock
from database import (
    EPSS_BACKFILL_DONE_KEY,
    apply_additive_cve_enrichments,
    delete_cves_by_ids,
    purge_legacy_rejected_cves,
    refresh_all_cve_ai_context,
    backfill_display_fields,
    backfill_has_poc,
    enrich_kev_summaries,
    get_all_cve_ids,
    get_cve_count,
    get_cves_needing_intel_enrichment,
    get_db,
    get_nvd_sync_watermark,
    get_sync_state_value,
    insert_epss_history_rows,
    mark_cves_as_kev,
    resolve_nvd_watermark,
    set_nvd_sync_watermark,
    set_sync_state_value,
    snapshot_epss_scores,
    strip_auto_generated_summaries,
    update_epss_scores,
    upsert_cve,
    upsert_cves,
    upsert_kev,
)
from feeds.cvelistv5 import SYNC_STATE_KEY as CVELISTV5_SYNC_STATE_KEY
from feeds.cvelistv5 import fetch_cvelistv5_delta, get_cvelistv5_sync_interval_minutes
from feeds.vulnrichment import fetch_vulnrichment_enrichments, get_vulnrichment_sync_interval_hours
from feeds.epss import BACKFILL_BATCH_SIZE, BACKFILL_THROTTLE_SECONDS, fetch_epss_time_series_batch
from feeds.case_study_feed import (
    build_incident_feed_snapshot,
    get_incident_feed_refresh_minutes,
)
from feeds.nvd import fetch_cve_by_id, fetch_nvd_cve_updates
from feeds.kev import fetch_kev
from feeds.epss import fetch_epss
from feeds.atlas import get_latest_atlas_release, refresh_atlas_data
from feeds.mitre import refresh_mitre_data
from feeds.exploit_sync import (
    exploit_sources_enabled,
    get_exploit_sources_interval_hours,
    sync_all_exploit_sources,
)
from ml.embeddings import embeddings_enabled, run_embeddings_backfill
from ml.product_extraction import (
    llm_product_extraction_enabled,
    run_llm_product_extraction,
)
from detection.context_sync import (
    detection_context_sync_enabled,
    run_detection_context_sync,
)
from webhooks.alerts import check_backup_deadman, get_backup_interval_hours, process_kev_stack_alerts
from backup.manager import run_backup

logger = logging.getLogger(__name__)

SCHEDULER_REFRESH_TZ = "Asia/Kolkata"

_scheduler: AsyncIOScheduler | None = None
# Job-keyed locks live in scheduler_locks.py (shared with routers/admin.py so
# the two can't drift out of sync). This one has no APScheduler job ID, so it
# stays private here.
_epss_backfill_lock = asyncio.Lock()

# Cap concurrent background jobs that hold pool connections (Postgres).
_SCHEDULER_DB_CONCURRENCY = max(1, int(os.environ.get("SCHEDULER_DB_CONCURRENCY", "3")))
_scheduler_db_sem = asyncio.Semaphore(_SCHEDULER_DB_CONCURRENCY)


def _schedule_background(coro) -> asyncio.Task:
    """Run a coroutine under the scheduler DB concurrency limit."""

    async def _guarded() -> None:
        async with _scheduler_db_sem:
            await coro

    return asyncio.create_task(_guarded())


async def _with_db(coro):
    """Acquire a DB connection for a short coroutine, then release."""
    db = await get_db()
    try:
        return await coro(db)
    finally:
        await db.close()


# Live progress messages for currently-running jobs, keyed by job ID.
# Jobs write here via the _progress callback pattern to avoid circular imports.
_job_progress: dict[str, str] = {}


def any_ingest_lock_held() -> bool:
    """True when any ingest-related lock is held (used by /api/admin/system)."""
    return any_locked() or _epss_backfill_lock.locked()


async def _write_job_last_run(
    job_id: str,
    start: datetime,
    records: int = 0,
    had_error: bool = False,
    error_message: str = "",
) -> None:
    """Best-effort: persist last-run metadata (ring of 5) to sync_state."""
    import json as _json

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    new_entry = {
        "started_at": start.isoformat(timespec="seconds"),
        # keep legacy key for backward compat with older admin.py readers
        "last_run_utc": start.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 2),
        "records_upserted": records,
        "had_error": had_error,
        "error_message": error_message[:500] if error_message else "",
    }
    for attempt in range(4):
        try:
            db = await get_db()
            try:
                existing_raw = await get_sync_state_value(db, f"scheduler.last_run.{job_id}")
                history: list = []
                if existing_raw:
                    try:
                        parsed = _json.loads(existing_raw)
                        if isinstance(parsed, list):
                            history = parsed
                        elif isinstance(parsed, dict):
                            # Migrate old single-dict format to array
                            history = [parsed]
                    except Exception:
                        history = []
                history.insert(0, new_entry)
                history = history[:5]
                await set_sync_state_value(
                    db,
                    f"scheduler.last_run.{job_id}",
                    _json.dumps(history),
                )
                await db.commit()
            finally:
                await db.close()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 3:
                logger.warning(
                    "Failed to write job last-run state for %s: %s", job_id, exc
                )
                return
            await asyncio.sleep(0.25 * (attempt + 1))
        except Exception as exc:
            logger.warning("Failed to write job last-run state for %s: %s", job_id, exc)
            return


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
    """Backward-compatible schedule hint (NVD hourly cadence)."""
    intervals = get_ingest_intervals()
    return {
        "hour": int(os.environ.get("CACHE_REFRESH_HOUR", "6")),
        "minute": int(os.environ.get("CACHE_REFRESH_MINUTE", "0")),
        "timezone": intervals["timezone"],
        "nvd_interval_hours": intervals["nvd_hours"],
        "kev_interval_minutes": intervals["kev_minutes"],
        "epss_interval_hours": intervals["epss_hours"],
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
    return (
        get_lock("nvd_incremental_sync").locked()
        or get_lock("kev_metadata_sync").locked()
        or get_lock("epss_score_sync").locked()
    )


def refresh_in_progress() -> bool:
    """Alias for API compatibility."""
    return ingest_in_progress()


def get_ingest_status() -> dict:
    return {
        "nvd_in_progress": get_lock("nvd_incremental_sync").locked(),
        "kev_in_progress": get_lock("kev_metadata_sync").locked(),
        "epss_in_progress": get_lock("epss_score_sync").locked(),
        "mitre_in_progress": get_lock("weekly_mitre_refresh").locked(),
        "any_in_progress": ingest_in_progress(),
        "intervals": get_ingest_intervals(),
    }


async def run_nvd_incremental_sync() -> bool:
    if get_lock("nvd_incremental_sync").locked():
        logger.warning("NVD sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with get_lock("nvd_incremental_sync"):
            _job_progress["nvd_incremental_sync"] = "Resolving NVD sync watermark…"
            await _run_nvd_incremental_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
        _job_progress.pop("nvd_incremental_sync", None)
        await _write_job_last_run("nvd_incremental_sync", _start, had_error=_had_error, error_message=_error_msg)
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

        _job_progress["nvd_incremental_sync"] = f"Fetching CVE updates from NVD API (watermark: {watermark or 'full window'})…"
        cves, mod_end_iso, used_incremental, rejected_ids = await fetch_nvd_cve_updates(
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
            _job_progress["nvd_incremental_sync"] = f"Writing {len(cves)} CVEs to database, purging {len(rejected_ids)} rejected IDs…"
            legacy_purged = await purge_legacy_rejected_cves(db)
            rejected_purged = await delete_cves_by_ids(db, rejected_ids)
            if legacy_purged or rejected_purged:
                logger.info(
                    "NVD sync purged %d rejected CVE row(s) (%d legacy, %d from feed)",
                    legacy_purged + rejected_purged,
                    legacy_purged,
                    rejected_purged,
                )
            await upsert_cves(db, cves)
            new_or_updated = len(cves)
            await set_nvd_sync_watermark(db, new_watermark)
            updated_ids = [
                (cve.get("cve_id") or "").upper()
                for cve in cves
                if cve.get("cve_id")
            ]
            if updated_ids:
                _job_progress["nvd_incremental_sync"] = f"Post-processing {len(updated_ids)} CVEs: stripping stale summaries, backfilling display fields…"
                stripped = await strip_auto_generated_summaries(db, updated_ids)
                filled = await backfill_display_fields(db, updated_ids)
                poc_marked = await backfill_has_poc(db, updated_ids)
            else:
                stripped = filled = poc_marked = 0
            if updated_ids:
                _job_progress["nvd_incremental_sync"] = f"Cross-enriching {len(updated_ids)} CVEs via Sploitus and CIRCL exploit references…"
                from feeds.extended import enrich_cves_extended

                ext_stats = await enrich_cves_extended(db, updated_ids)
                logger.info(
                    "Extended enrichment: Sploitus %d, CIRCL %d",
                    ext_stats.get("sploitus", 0),
                    ext_stats.get("circl", 0),
                )
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
    if get_lock("kev_metadata_sync").locked():
        logger.warning("KEV sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with get_lock("kev_metadata_sync"):
            _job_progress["kev_metadata_sync"] = "Fetching CISA KEV catalog from CISA.gov…"
            await _run_kev_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
        _job_progress.pop("kev_metadata_sync", None)
        await _write_job_last_run("kev_metadata_sync", _start, had_error=_had_error, error_message=_error_msg)
    return True


async def _run_kev_sync() -> None:
    start_time = datetime.now(timezone.utc)
    logger.info("KEV metadata sync started at %s", start_time.isoformat())

    nvd_api_key = os.environ.get("NVD_API_KEY")
    kev_count = 0
    newly_kev: list[str] = []

    try:
        kev_entries = await fetch_kev()
        _job_progress["kev_metadata_sync"] = f"Writing {len(kev_entries)} KEV catalog entries, marking CVEs as exploited-in-wild…"

        db = await get_db()
        try:
            kev_ids = []
            for entry in kev_entries:
                await upsert_kev(db, entry)
                cve_id = entry.get("cveID", "")
                if cve_id:
                    kev_ids.append(cve_id)
                    kev_count += 1
            newly_kev = await mark_cves_as_kev(db, kev_ids)
            _job_progress["kev_metadata_sync"] = f"Enriching KEV summaries from CISA descriptions ({len(newly_kev)} newly flagged CVEs)…"
            kev_summaries = await enrich_kev_summaries(db)
            await db.commit()
            if kev_summaries:
                logger.info("Enriched %d KEV summaries from CISA descriptions", kev_summaries)
        finally:
            await db.close()

        if newly_kev:
            try:
                _job_progress["kev_metadata_sync"] = f"Sending KEV-on-stack webhook alerts for {len(newly_kev)} newly exploited CVEs…"
                alerted = await process_kev_stack_alerts(newly_kev)
                if alerted:
                    logger.info("KEV-on-stack alerts sent: %d", alerted)
            except Exception as exc:
                logger.error("KEV-on-stack alert processing failed: %s", exc)

        logger.info("KEV sync complete: %d catalog entries processed", kev_count)

        if os.environ.get("KEV_CROSS_FETCH_NVD", "1").strip().lower() in ("1", "true", "yes"):
            _job_progress["kev_metadata_sync"] = "Cross-fetching KEV CVEs missing from NVD database…"
            await _cross_fetch_missing_kev_cves(kev_entries, nvd_api_key)

    except Exception as exc:
        logger.error("KEV sync failed: %s", exc)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("KEV metadata sync finished in %.1fs", duration)


async def _cross_fetch_missing_kev_cves(kev_entries: list[dict], nvd_api_key: str | None) -> None:
    try:
        missing_kev: list[str] = []
        kev_short_map: dict[str, str] = {}

        async def _load_missing(db):
            nonlocal missing_kev, kev_short_map
            existing_ids = set(await get_all_cve_ids(db))
            missing_kev = [
                e.get("cveID", "")
                for e in kev_entries
                if e.get("cveID") and e.get("cveID") not in existing_ids
            ]
            kev_short_map = {
                e.get("cveID", ""): e.get("shortDescription", "") for e in kev_entries
            }

        await _with_db(_load_missing)
        if not missing_kev:
            return

        logger.info("KEV cross-fetch: %d CVEs missing from cves table", len(missing_kev))
        kev_cross_fetched = 0
        for kev_cve_id in missing_kev:
            try:
                cve_data = await fetch_cve_by_id(kev_cve_id, nvd_api_key)
                if not cve_data:
                    continue
                cve_data["is_kev"] = True
                kev_short = kev_short_map.get(kev_cve_id, "")
                if kev_short:
                    cve_data["summary"] = kev_short

                async def _upsert(db, payload=cve_data):
                    await upsert_cve(db, payload)
                    await db.commit()

                await _with_db(_upsert)
                kev_cross_fetched += 1
            except Exception as exc:
                logger.error("KEV cross-fetch failed for %s: %s", kev_cve_id, exc)
            await asyncio.sleep(1)
        logger.info("KEV cross-fetch complete: %d CVEs inserted", kev_cross_fetched)
    except Exception as exc:
        logger.error("KEV cross-fetch step failed: %s", exc)


async def run_epss_sync() -> bool:
    if get_lock("epss_score_sync").locked():
        logger.warning("EPSS sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with get_lock("epss_score_sync"):
            _job_progress["epss_score_sync"] = "Loading CVE IDs from database…"
            await _run_epss_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
        _job_progress.pop("epss_score_sync", None)
        await _write_job_last_run("epss_score_sync", _start, had_error=_had_error, error_message=_error_msg)
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

        _job_progress["epss_score_sync"] = f"Fetching EPSS exploit-probability scores for {len(all_cve_ids)} CVEs from FIRST.org…"
        scores = await fetch_epss(all_cve_ids)
        epss_updated = len(scores)

        db = await get_db()
        try:
            _job_progress["epss_score_sync"] = f"Snapshotting current EPSS scores for delta tracking, then writing {len(scores)} updated scores…"
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


async def run_epss_backfill() -> bool:
    """One-shot EPSS history backfill — idempotent, skipped once marker is set.

    Fetches daily EPSS scores for every CVE already in the DB using the FIRST
    API ``scope=time-series``, batched at BACKFILL_BATCH_SIZE CVEs per request
    and throttled to stay well below 1,000 req/min.  On restart the
    ``INSERT OR IGNORE`` ensures no duplicate rows; the ``epss_backfill_done``
    marker prevents re-work once the full job completes.
    """
    if _epss_backfill_lock.locked():
        logger.info("EPSS backfill already in progress — skipping")
        return False

    async with _epss_backfill_lock:
        _job_progress["epss_backfill"] = "Loading CVE IDs for EPSS historical backfill…"
        await _run_epss_backfill()
    _job_progress.pop("epss_backfill", None)
    return True


async def _run_epss_backfill() -> None:
    start = datetime.now(timezone.utc)
    logger.info("EPSS history backfill started at %s", start.isoformat())

    total_rows = 0
    batch_num = 0
    total_batches = 0
    all_cve_ids: list[str] = []

    async def _load_state(db):
        nonlocal all_cve_ids, total_batches
        done = await get_sync_state_value(db, EPSS_BACKFILL_DONE_KEY)
        if done:
            return "done"
        all_cve_ids = await get_all_cve_ids(db)
        if not all_cve_ids:
            await set_sync_state_value(db, EPSS_BACKFILL_DONE_KEY, "1")
            await db.commit()
            return "empty"
        total_batches = (len(all_cve_ids) + BACKFILL_BATCH_SIZE - 1) // BACKFILL_BATCH_SIZE
        return "run"

    try:
        state = await _with_db(_load_state)
        if state == "done":
            logger.info("EPSS backfill: marker %r already set — skipping", EPSS_BACKFILL_DONE_KEY)
            return
        if state == "empty":
            logger.info("EPSS backfill: DB has no CVEs — marking done immediately")
            return

        logger.info(
            "EPSS backfill: %d CVEs → %d batches (size=%d, throttle=%.1fs)",
            len(all_cve_ids),
            total_batches,
            BACKFILL_BATCH_SIZE,
            BACKFILL_THROTTLE_SECONDS,
        )

        for offset in range(0, len(all_cve_ids), BACKFILL_BATCH_SIZE):
            batch = all_cve_ids[offset : offset + BACKFILL_BATCH_SIZE]
            _job_progress["epss_backfill"] = f"Fetching EPSS time-series history: batch {batch_num + 1}/{total_batches} ({offset + len(batch)}/{len(all_cve_ids)} CVEs)…"
            rows = await fetch_epss_time_series_batch(batch)
            if rows:

                async def _insert(db, payload=rows):
                    nonlocal total_rows
                    inserted = await insert_epss_history_rows(db, payload)
                    await db.commit()
                    total_rows += inserted

                await _with_db(_insert)

            batch_num += 1
            if batch_num % 10 == 0 or batch_num == total_batches:
                logger.info(
                    "EPSS backfill: %d/%d batches done (%d history rows inserted so far)",
                    batch_num,
                    total_batches,
                    total_rows,
                )

            if offset + BACKFILL_BATCH_SIZE < len(all_cve_ids):
                await asyncio.sleep(BACKFILL_THROTTLE_SECONDS)

        async def _mark_done(db):
            await set_sync_state_value(db, EPSS_BACKFILL_DONE_KEY, "1")
            await db.commit()

        await _with_db(_mark_done)

        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            "EPSS backfill complete: %d CVEs, %d history rows inserted in %.1fs",
            len(all_cve_ids),
            total_rows,
            duration,
        )
    except Exception as exc:
        logger.error(
            "EPSS backfill aborted at batch %d/%d: %s — will retry on next startup",
            batch_num,
            total_batches,
            exc,
        )


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
    if get_lock("weekly_mitre_refresh").locked():
        logger.warning("MITRE refresh already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    async with get_lock("weekly_mitre_refresh"):
        start = _start
        logger.info("Weekly MITRE ATT&CK + ATLAS refresh started at %s", start.isoformat())
        ok = True
        try:
            stats = await refresh_mitre_data()
            atlas_stats = await refresh_atlas_data()
            db = await get_db()
            try:
                _job_progress["weekly_mitre_refresh"] = "Refreshing MITRE ATT&CK technique catalog and CVE technique mappings…"
                stats = await refresh_mitre_data(db)
                _job_progress["weekly_mitre_refresh"] = "Refreshing ATLAS AI security matrix techniques and case studies…"
                atlas_stats = await refresh_atlas_data(db)
                _job_progress["weekly_mitre_refresh"] = "Updating CVE AI context flags and ATLAS technique links across database…"
                ai_stats = await refresh_all_cve_ai_context(db)
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
            logger.info(
                "AI context refresh: %d CVEs flagged, %d ATLAS links",
                ai_stats.get("cves_flagged", 0),
                ai_stats.get("atlas_links", 0),
            )
        except Exception as exc:
            logger.error("Weekly MITRE/ATLAS refresh failed: %s", exc)
            ok = False
            _mitre_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _mitre_error_msg = ""
        _job_progress.pop("weekly_mitre_refresh", None)
        await _write_job_last_run("weekly_mitre_refresh", _start, had_error=not ok, error_message=_mitre_error_msg)
        return ok


async def run_atlas_version_check() -> bool:
    """Check upstream ATLAS releases.atom for a new version and refresh if found."""
    from database import ATLAS_UPSTREAM_VERSION_KEY, get_sync_state_value, set_sync_state_value

    if get_lock("atlas_version_check").locked():
        logger.warning("ATLAS version check already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    async with get_lock("atlas_version_check"):
        ok = True
        error_msg = ""
        try:
            _job_progress["atlas_version_check"] = "Fetching ATLAS upstream release feed from mitre-atlas.github.io…"
            latest = await get_latest_atlas_release()
            if latest is None:
                logger.warning("ATLAS version check: could not fetch upstream release feed")
                return False

            db = await get_db()
            try:
                stored = await get_sync_state_value(db, ATLAS_UPSTREAM_VERSION_KEY)
                if stored == latest:
                    logger.info("ATLAS version check: up to date (%s)", latest)
                    _job_progress.pop("atlas_version_check", None)
                    return False

                logger.info("ATLAS version check: new release %s (was %s) — refreshing", latest, stored)
                _job_progress["atlas_version_check"] = f"New ATLAS release {latest} detected (was {stored}) — triggering MITRE/ATLAS refresh…"
            finally:
                await db.close()

            refreshed = await run_weekly_mitre_refresh()
            if not refreshed:
                ok = False
                error_msg = "weekly_mitre_refresh did not complete"
                return False

            _job_progress["atlas_version_check"] = f"Storing new ATLAS version marker ({latest})…"
            db = await get_db()
            try:
                await set_sync_state_value(db, ATLAS_UPSTREAM_VERSION_KEY, latest)
                await db.commit()
            finally:
                await db.close()
            return True
        except Exception as exc:
            logger.error("ATLAS version check failed: %s", exc)
            ok = False
            error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
            return False
        finally:
            _job_progress.pop("atlas_version_check", None)
            await _write_job_last_run("atlas_version_check", _start, had_error=not ok, error_message=error_msg)


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
        _schedule_background(run_weekly_mitre_refresh())
    else:
        logger.info("MITRE techniques loaded (%d rows), ATLAS (%d rows)", mitre_count, atlas_count)


async def _run_startup_summary_maintenance() -> None:
    """Strip auto-generated summaries and backfill KEV text — runs off the hot path."""
    from database import enrich_kev_summaries, strip_auto_generated_summaries

    db = await get_db()
    try:
        stripped = await strip_auto_generated_summaries(db)
        await enrich_kev_summaries(db)
        await db.commit()
        if stripped:
            logger.info(
                "Startup: cleared %d auto-generated plain summaries", stripped
            )
    except Exception:
        logger.exception("Startup summary maintenance failed")
    finally:
        await db.close()


async def _run_deferred_startup_jobs() -> None:
    """Run heavy startup maintenance sequentially — avoids pool stampedes."""
    await _run_startup_summary_maintenance()
    await run_epss_backfill()
    if exploit_sources_enabled():
        await run_exploit_sources_sync()


async def maybe_run_on_startup() -> None:
    count = 0
    db = await get_db()
    try:
        count = await get_cve_count(db)
    finally:
        await db.close()

    if count < 10:
        logger.info("CVE table has %d rows (< 10). Running full ingest on startup.", count)
        _schedule_background(run_full_ingest_sync())
    else:
        _schedule_background(_run_deferred_startup_jobs())
        logger.info(
            "CVE table has %d rows. Deferred startup maintenance scheduled.",
            count,
        )

    await maybe_run_mitre_on_startup()


async def run_exploit_sources_sync() -> bool:
    """Daily exploit-availability feeds: PoC-in-GitHub, ExploitDB, Metasploit, Nuclei."""
    if not exploit_sources_enabled():
        logger.info("Exploit sources sync disabled (EXPLOIT_SOURCES_SYNC_ENABLED=0)")
        return False

    if get_lock("exploit_sources_sync").locked():
        logger.warning("Exploit sources sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("exploit_sources_sync"):
        start = _start
        logger.info("Exploit sources sync started at %s", start.isoformat())
        try:
            def _exploit_progress(msg: str) -> None:
                _job_progress["exploit_sources_sync"] = msg
            stats = await sync_all_exploit_sources(progress_cb=_exploit_progress)
            if stats:
                logger.info(
                    "Exploit sources sync complete: PoC-GitHub %s, ExploitDB %s, "
                    "Metasploit %s, Nuclei %s (has_poc marked: %s)",
                    stats.get("poc_github", {}),
                    stats.get("exploitdb", {}),
                    stats.get("metasploit", {}),
                    stats.get("nuclei", {}),
                    (stats.get("has_poc_marked") or {}).get("count", 0),
                )
        except Exception as exc:
            logger.error("Exploit sources sync failed: %s", exc)
            _had_error = True
            _exploit_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _exploit_error_msg = ""
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Exploit sources sync finished in %.1fs", duration)
    await _write_job_last_run("exploit_sources_sync", _start, had_error=_had_error, error_message=_exploit_error_msg)
    return True


async def run_vulnrichment_sync() -> bool:
    if get_lock("vulnrichment_snapshot_sync").locked():
        logger.warning("Vulnrichment sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("vulnrichment_snapshot_sync"):
        start = _start
        logger.info("Vulnrichment snapshot sync started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                _job_progress["vulnrichment_snapshot_sync"] = "Identifying CVEs with missing CWE/CVSS/CPE intel enrichments…"
                gap_ids = await get_cves_needing_intel_enrichment(db, limit=1000)
            finally:
                await db.close()

            target = set(gap_ids) if gap_ids else None
            _job_progress["vulnrichment_snapshot_sync"] = f"Fetching CISA Vulnrichment enrichments for {len(gap_ids)} CVEs from GitHub snapshot…"
            enrichments = await fetch_vulnrichment_enrichments(target)
            if not enrichments:
                logger.info("Vulnrichment sync: no enrichments to apply")
                _job_progress.pop("vulnrichment_snapshot_sync", None)
                await _write_job_last_run("vulnrichment_snapshot_sync", _start)
                return True

            _job_progress["vulnrichment_snapshot_sync"] = f"Applying {len(enrichments)} Vulnrichment records (CWE, CVSS, CPE metadata) to database…"
            db = await get_db()
            try:
                applied = await apply_additive_cve_enrichments(db, enrichments)
                await db.commit()
            finally:
                await db.close()

            logger.info("Vulnrichment sync complete: %d CVE rows updated", applied)
        except Exception as exc:
            logger.error("Vulnrichment sync failed: %s", exc)
            _had_error = True
            _vuln_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _vuln_error_msg = ""
        finally:
            _job_progress.pop("vulnrichment_snapshot_sync", None)
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Vulnrichment snapshot sync finished in %.1fs", duration)
    await _write_job_last_run("vulnrichment_snapshot_sync", _start, had_error=_had_error, error_message=_vuln_error_msg)
    return True


async def run_cvelistv5_sync() -> bool:
    if get_lock("cvelistv5_incremental_sync").locked():
        logger.warning("cvelistV5 sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("cvelistv5_incremental_sync"):
        start = _start
        logger.info("cvelistV5 incremental sync started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                watermark = await get_sync_state_value(db, CVELISTV5_SYNC_STATE_KEY)
            finally:
                await db.close()

            _job_progress["cvelistv5_incremental_sync"] = f"Fetching cvelistV5 delta from GitHub (since commit {(watermark or 'HEAD')[:12]})…"
            records, rejected_ids, new_head, advance = await fetch_cvelistv5_delta(watermark)
            if not advance or not new_head:
                _job_progress.pop("cvelistv5_incremental_sync", None)
                await _write_job_last_run("cvelistv5_incremental_sync", _start)
                return True

            applied = 0
            purged = 0
            db = await get_db()
            try:
                if records:
                    _job_progress["cvelistv5_incremental_sync"] = f"Applying {len(records)} cvelistV5 CVE record updates (descriptions, CWEs, references)…"
                    applied = await apply_additive_cve_enrichments(db, records)
                if rejected_ids:
                    _job_progress["cvelistv5_incremental_sync"] = f"Purging {len(rejected_ids)} CVEs rejected by cvelistV5 maintainers…"
                    purged = await delete_cves_by_ids(db, rejected_ids)
                await set_sync_state_value(db, CVELISTV5_SYNC_STATE_KEY, new_head)
                await db.commit()
            finally:
                await db.close()

            logger.info(
                "cvelistV5 sync complete: %d CVE rows updated, %d rejected purged, watermark=%s",
                applied,
                purged,
                new_head[:12],
            )
        except Exception as exc:
            logger.error("cvelistV5 sync failed: %s", exc)
            _had_error = True
            _cvelist_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _cvelist_error_msg = ""
        finally:
            _job_progress.pop("cvelistv5_incremental_sync", None)
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("cvelistV5 incremental sync finished in %.1fs", duration)
    await _write_job_last_run("cvelistv5_incremental_sync", _start, had_error=_had_error, error_message=_cvelist_error_msg)
    return True


async def run_incident_feed_refresh() -> bool:
    """Rebuild the combined Incidents & News snapshot (RSS in parallel + ATLAS)."""
    _start = datetime.now(timezone.utc)
    _had_error = False
    try:
        snapshot = await build_incident_feed_snapshot()
        logger.info(
            "Incident feed snapshot refresh complete: %d news, %d ATLAS, %d errors",
            len(snapshot.get("news") or []),
            len(snapshot.get("atlas") or []),
            len(snapshot.get("errors") or []),
        )
    except Exception as exc:
        logger.error("Incident feed snapshot refresh failed: %s", exc)
        _had_error = True
        _incident_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
    else:
        _incident_error_msg = ""
    await _write_job_last_run("incident_feed_refresh", _start, had_error=_had_error, error_message=_incident_error_msg)
    return True


async def run_nightly_correlation() -> bool:
    """Nightly correlation engine: infrastructure, actor, and temporal analysis."""
    if get_lock("nightly_correlation").locked():
        logger.warning("Correlation job already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("nightly_correlation"):
        from correlation.engine import (
            prefetch_pulse_iocs_for_nightly,
            run_nightly_correlation as _run_correlation,
        )

        api_key = os.environ.get("OTX_API_KEY", "")
        if api_key:
            _job_progress["nightly_correlation"] = "Pre-fetching OTX pulse IOCs to warm Level 1 infrastructure correlation…"
            ioc_count = await prefetch_pulse_iocs_for_nightly(api_key)
            if ioc_count:
                logger.info("Pre-fetched IOCs for %d pulses", ioc_count)

        db = await get_db()
        try:
            def _corr_progress(msg: str) -> None:
                _job_progress["nightly_correlation"] = msg
            stats = await _run_correlation(db, progress_cb=_corr_progress)

            logger.info(
                "Nightly correlation: %d CVEs, %d infra pairs, %d actors, %d anomalies, "
                "%d campaigns",
                stats.get("cves_processed", 0),
                stats.get("infrastructure_pairs", 0),
                stats.get("actor_findings", 0),
                stats.get("temporal_anomalies", 0),
                stats.get("campaigns_built", 0),
            )
        except Exception as exc:
            logger.error("Nightly correlation job failed: %s", exc, exc_info=True)
            _had_error = True
            _corr_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
            if hasattr(db, "rollback"):
                try:
                    await db.rollback()
                except Exception as rollback_exc:
                    logger.warning(
                        "Failed to rollback database transaction on job failure: %s",
                        rollback_exc,
                    )
        else:
            _corr_error_msg = ""
        finally:
            await db.close()
            _job_progress.pop("nightly_correlation", None)
    await _write_job_last_run("nightly_correlation", _start, had_error=_had_error, error_message=_corr_error_msg)
    return True


async def run_otx_nightly_sync() -> bool:
    if get_lock("otx_nightly_correlation").locked():
        logger.warning("OTX nightly correlation already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("otx_nightly_correlation"):
        api_key = os.environ.get("OTX_API_KEY", "")
        if not api_key:
            logger.info("OTX_API_KEY not set — skipping nightly correlation")
            await _write_job_last_run("otx_nightly_correlation", _start)
            return False
        db = None
        try:
            db = await get_db()
            from feeds.otx import run_otx_nightly_correlation

            def _otx_progress(msg: str) -> None:
                _job_progress["otx_nightly_correlation"] = msg
            stats = await run_otx_nightly_correlation(db, api_key, progress_cb=_otx_progress)
            await db.commit()

            logger.info(
                "OTX nightly correlation complete: %d CVEs, %d pulses cached",
                stats.get("cves", 0),
                stats.get("pulses", 0),
            )
        except Exception as exc:
            logger.error("OTX nightly correlation failed: %s", exc)
            _had_error = True
            _otx_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _otx_error_msg = ""
        finally:
            if db is not None:
                await db.close()
            _job_progress.pop("otx_nightly_correlation", None)
    await _write_job_last_run("otx_nightly_correlation", _start, had_error=_had_error, error_message=_otx_error_msg)
    return True


async def run_otx_continuous_sync() -> bool:
    """Continuous OTX pulse + IOC prefetch within hourly API budget."""
    from feeds.otx_continuous import otx_continuous_enabled, run_otx_continuous_sync as _run

    if not otx_continuous_enabled():
        return False
    if get_lock("otx_continuous_sync").locked():
        logger.info("OTX continuous sync already in progress — skipping")
        return False

    api_key = os.environ.get("OTX_API_KEY", "")
    if not api_key:
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _records = 0
    async with get_lock("otx_continuous_sync"):
        try:
            stats = await _run(api_key)
            _records = int(stats.get("api_calls") or 0)
            logger.info(
                "OTX continuous sync: %d API calls, %d CVE pulse batches, %d pulse IOCs (%s)",
                _records,
                stats.get("cve_pulses_stored", 0),
                stats.get("pulse_iocs_fetched", 0),
                stats.get("stop_reason", ""),
            )
        except Exception as exc:
            logger.error("OTX continuous sync failed: %s", exc)
            _had_error = True
            _otx_cont_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _otx_cont_error_msg = ""
    await _write_job_last_run(
        "otx_continuous_sync",
        _start,
        records=_records,
        had_error=_had_error,
        error_message=_otx_cont_error_msg,
    )
    return True


async def run_embeddings_sync() -> bool:
    """Embed CVE descriptions missing vectors (V1.3 Theme 7).

    No-op unless EMBEDDINGS_ENABLED=1 — the env gate is checked at run time
    so the operator can toggle without re-registering jobs. CPU-only model
    inference happens here (scheduler-side), never on the request path.
    """
    if not embeddings_enabled():
        return False
    if get_lock("embeddings_backfill").locked():
        logger.info("Embeddings backfill already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _embedded = 0
    async with get_lock("embeddings_backfill"):
        start = _start
        logger.info("Embeddings backfill started at %s", start.isoformat())
        stats: dict = {}
        try:
            db = await get_db()
            try:
                def _emb_progress(msg: str) -> None:
                    _job_progress["embeddings_backfill"] = msg
                stats = await run_embeddings_backfill(db, progress_cb=_emb_progress)
                _embedded = int(stats.get("embedded", 0))
            finally:
                await db.close()
                _job_progress.pop("embeddings_backfill", None)
            logger.info(
                "Embeddings backfill complete: %d CVEs embedded (model=%s) in %.1fs",
                _embedded,
                stats.get("model", ""),
                (datetime.now(timezone.utc) - start).total_seconds(),
            )
        except Exception as exc:
            logger.error("Embeddings backfill failed: %s", exc)
            _had_error = True
            _emb_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _emb_error_msg = ""
    await _write_job_last_run(
        "embeddings_backfill",
        _start,
        records=_embedded,
        had_error=_had_error,
        error_message=_emb_error_msg,
    )
    return True


async def run_llm_extraction_sync() -> bool:
    """LLM product extraction for NVD-unanalyzed CVEs (V1.3 Theme 7).

    No-op unless LLM_PRODUCT_EXTRACTION_ENABLED=1 AND an LLM provider key is set.
    """
    if not llm_product_extraction_enabled():
        return False
    if get_lock("llm_product_extraction").locked():
        logger.info("LLM product extraction already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with get_lock("llm_product_extraction"):
        start = _start
        logger.info("LLM product extraction started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                def _progress(msg: str) -> None:
                    _job_progress["llm_product_extraction"] = msg
                stats = await run_llm_product_extraction(db, progress_cb=_progress)
            finally:
                await db.close()
                _job_progress.pop("llm_product_extraction", None)

            logger.info(
                "LLM product extraction complete: %d candidates, %d extracted, "
                "%d written, %d errors in %.1fs",
                stats.get("candidates", 0),
                stats.get("extracted", 0),
                stats.get("written", 0),
                stats.get("errors", 0),
                (datetime.now(timezone.utc) - start).total_seconds(),
            )
        except Exception as exc:
            logger.error("LLM product extraction failed: %s", exc)
            _had_error = True
            _llm_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _llm_error_msg = ""
    await _write_job_last_run("llm_product_extraction", _start, had_error=_had_error, error_message=_llm_error_msg)
    return True


async def run_detection_context_sync_job() -> bool:
    """Backfill DetectionContext cache rows (Sprint D2).

    No-op unless DETECTION_CONTEXT_SYNC_ENABLED=1 — static metadata only,
    no LLM. Scheduler-side only, never on the request path.
    """
    if not detection_context_sync_enabled():
        return False
    if get_lock("detection_context_sync").locked():
        logger.info("DetectionContext sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _written = 0
    async with get_lock("detection_context_sync"):
        start = _start
        logger.info("DetectionContext sync started at %s", start.isoformat())
        stats: dict = {}
        try:
            db = await get_db()
            try:
                def _progress(msg: str) -> None:
                    _job_progress["detection_context_sync"] = msg

                stats = await run_detection_context_sync(db, progress_cb=_progress)
                _written = int(stats.get("written", 0))
                await db.commit()
            finally:
                await db.close()
                _job_progress.pop("detection_context_sync", None)
            logger.info(
                "DetectionContext sync complete: %d candidates, %d written in %.1fs",
                stats.get("candidates", 0),
                _written,
                (datetime.now(timezone.utc) - start).total_seconds(),
            )
        except Exception as exc:
            logger.error("DetectionContext sync failed: %s", exc)
            _had_error = True
            _ctx_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        else:
            _ctx_error_msg = ""
    await _write_job_last_run(
        "detection_context_sync",
        _start,
        records=_written,
        had_error=_had_error,
        error_message=_ctx_error_msg,
    )
    return True


async def run_scheduled_backup() -> bool:
    """Scheduler hook: create a backup archive and prune old ones, on
    BACKUP_INTERVAL_HOURS. run_backup() itself no-ops when BACKUP_ENABLED=0
    and applies BACKUP_RETENTION_COUNT pruning — this just wires it to a job."""
    if get_lock("scheduled_backup").locked():
        logger.info("Scheduled backup already in progress — skipping")
        return False
    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    async with get_lock("scheduled_backup"):
        try:
            _job_progress["scheduled_backup"] = "Creating database backup archive and pruning old backups…"
            await asyncio.to_thread(run_backup, reason="scheduled")
        except Exception as exc:
            logger.error("Scheduled backup failed: %s", exc)
            _had_error = True
            _error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        finally:
            _job_progress.pop("scheduled_backup", None)
    await _write_job_last_run("scheduled_backup", _start, had_error=_had_error, error_message=_error_msg)
    return not _had_error


async def run_backup_deadman_check() -> bool:
    """Scheduler hook: warn when backups are overdue (2× interval)."""
    _start = datetime.now(timezone.utc)
    _had_error = False
    _deadman_error_msg = ""
    try:
        result = await check_backup_deadman()
        return result
    except Exception as exc:
        logger.error("Backup dead-man check failed: %s", exc)
        _had_error = True
        _deadman_error_msg = (f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__)[:500]
        return False
    finally:
        await _write_job_last_run("backup_deadman_check", _start, had_error=_had_error, error_message=_deadman_error_msg)


async def run_session_cleanup() -> int:
    """Scheduler hook: purge expired built-in-login sessions (decision 2026-06-11)."""
    from auth.repo import purge_expired_sessions

    db = await get_db()
    try:
        purged = await purge_expired_sessions(db)
        await db.commit()
        return purged
    except Exception as exc:
        logger.error("Session cleanup failed: %s", exc)
        return 0
    finally:
        await db.close()


async def run_cache_retention_cleanup() -> dict[str, int]:
    """Scheduler hook: delete physically stale cache and overlay rows (Sprint C3)."""
    from database import run_retention_cleanup

    db = await get_db()
    try:
        stats = await run_retention_cleanup(db)
        await db.commit()
        if any(stats.values()):
            logger.info("Cache retention cleanup: %s", stats)
        return stats
    except Exception as exc:
        logger.error("Cache retention cleanup failed: %s", exc)
        return {}
    finally:
        await db.close()


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

    mitre_hour = int(os.environ.get("MITRE_REFRESH_HOUR", "2"))
    mitre_minute = int(os.environ.get("MITRE_REFRESH_MINUTE", "0"))
    scheduler.add_job(
        run_weekly_mitre_refresh,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=mitre_hour,
            minute=mitre_minute,
            timezone=sched_tz,
        ),
        id="weekly_mitre_refresh",
        name="Weekly MITRE ATT&CK + ATLAS Refresh",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        run_atlas_version_check,
        trigger=IntervalTrigger(hours=24, timezone=sched_tz),
        id="atlas_version_check",
        name="ATLAS Upstream Version Check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    otx_hour = int(os.environ.get("OTX_CORRELATION_HOUR", "2"))
    otx_minute = int(os.environ.get("OTX_CORRELATION_MINUTE", "0"))
    otx_tz = ZoneInfo(os.environ.get("OTX_CORRELATION_TIMEZONE", "Asia/Kolkata"))
    scheduler.add_job(
        run_otx_nightly_sync,
        trigger=CronTrigger(
            hour=otx_hour,
            minute=otx_minute,
            timezone=otx_tz,
        ),
        id="otx_nightly_correlation",
        name="OTX Nightly Campaign Correlation",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    from feeds.otx_continuous import get_otx_continuous_interval_minutes, otx_continuous_enabled

    if otx_continuous_enabled():
        otx_cont_minutes = get_otx_continuous_interval_minutes()
        scheduler.add_job(
            run_otx_continuous_sync,
            trigger=IntervalTrigger(minutes=otx_cont_minutes, timezone=sched_tz),
            id="otx_continuous_sync",
            name="OTX Continuous Pulse + IOC Sync",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(sched_tz) + timedelta(minutes=2),
        )

    incident_minutes = get_incident_feed_refresh_minutes()
    if os.environ.get("PLAYWRIGHT_SMOKE") != "1":
        scheduler.add_job(
            run_incident_feed_refresh,
            trigger=IntervalTrigger(minutes=incident_minutes, timezone=sched_tz),
            id="incident_feed_refresh",
            name="Incident Feed Snapshot Refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            # Warm the snapshot shortly after boot instead of waiting one interval.
            next_run_time=datetime.now(sched_tz) + timedelta(seconds=20),
        )

    exploit_hours = get_exploit_sources_interval_hours()
    if exploit_sources_enabled():
        scheduler.add_job(
            run_exploit_sources_sync,
            trigger=IntervalTrigger(hours=exploit_hours, timezone=sched_tz),
            id="exploit_sources_sync",
            name="Exploit Availability Sources Sync",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(sched_tz) + timedelta(minutes=30),
        )

    embeddings_hours = int(os.environ.get("EMBEDDINGS_SYNC_INTERVAL_HOURS", "6"))
    scheduler.add_job(
        run_embeddings_sync,
        trigger=IntervalTrigger(hours=embeddings_hours, timezone=sched_tz),
        id="embeddings_backfill",
        name="CVE Description Embeddings Backfill",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        # First pass shortly after boot when enabled; the run-time env gate
        # makes this a no-op while EMBEDDINGS_ENABLED=0 (the default).
        next_run_time=datetime.now(sched_tz) + timedelta(seconds=90),
    )

    llm_extraction_hours = int(
        os.environ.get("LLM_PRODUCT_EXTRACTION_INTERVAL_HOURS", "6")
    )
    scheduler.add_job(
        run_llm_extraction_sync,
        trigger=IntervalTrigger(hours=llm_extraction_hours, timezone=sched_tz),
        id="llm_product_extraction",
        name="LLM Product Extraction (NVD-unanalyzed CVEs)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(seconds=150),
    )

    detection_ctx_hours = int(
        os.environ.get("DETECTION_CONTEXT_SYNC_INTERVAL_HOURS", "6")
    )
    scheduler.add_job(
        run_detection_context_sync_job,
        trigger=IntervalTrigger(hours=detection_ctx_hours, timezone=sched_tz),
        id="detection_context_sync",
        name="DetectionContext Cache Backfill",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(seconds=120),
    )

    corr_hour = int(os.environ.get("CORRELATION_HOUR", "1"))
    corr_minute = int(os.environ.get("CORRELATION_MINUTE", "0"))
    corr_tz = ZoneInfo(os.environ.get("CORRELATION_TIMEZONE", "Asia/Kolkata"))
    scheduler.add_job(
        run_nightly_correlation,
        trigger=CronTrigger(
            hour=corr_hour,
            minute=corr_minute,
            timezone=corr_tz,
        ),
        id="nightly_correlation",
        name="BRIEFR Nightly Correlation Engine",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    vulnrichment_hours = get_vulnrichment_sync_interval_hours()
    scheduler.add_job(
        run_vulnrichment_sync,
        trigger=IntervalTrigger(hours=vulnrichment_hours, timezone=sched_tz),
        id="vulnrichment_snapshot_sync",
        name="CISA Vulnrichment Snapshot Sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(seconds=45),
    )

    cvelist_minutes = get_cvelistv5_sync_interval_minutes()
    scheduler.add_job(
        run_cvelistv5_sync,
        trigger=IntervalTrigger(minutes=cvelist_minutes, timezone=sched_tz),
        id="cvelistv5_incremental_sync",
        name="cvelistV5 Incremental Sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(seconds=60),
    )

    backup_hours = max(1, get_backup_interval_hours())
    scheduler.add_job(
        run_scheduled_backup,
        trigger=IntervalTrigger(hours=backup_hours, timezone=sched_tz),
        id="scheduled_backup",
        name="Scheduled Backup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(minutes=2),
    )
    scheduler.add_job(
        run_backup_deadman_check,
        trigger=IntervalTrigger(hours=max(1, backup_hours // 2), timezone=sched_tz),
        id="backup_deadman_check",
        name="Backup Dead-Man Check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(minutes=5),
    )

    scheduler.add_job(
        run_session_cleanup,
        trigger=IntervalTrigger(hours=24, timezone=sched_tz),
        id="session_cleanup",
        name="Expired Login Session Cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(minutes=10),
    )

    scheduler.add_job(
        run_cache_retention_cleanup,
        trigger=IntervalTrigger(hours=24, timezone=sched_tz),
        id="cache_retention_cleanup",
        name="Cache Retention Cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(sched_tz) + timedelta(minutes=15),
    )

    scheduler.start()
    _scheduler = scheduler

    async def _reapply_paused_jobs(sched: AsyncIOScheduler) -> None:
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT key, value FROM sync_state WHERE key LIKE 'scheduler.paused.%'"
            )
            for row in rows:
                job_id = row["key"].replace("scheduler.paused.", "")
                if row["value"] == "1":
                    job = sched.get_job(job_id)
                    if job:
                        job.pause()
        finally:
            await db.close()

    asyncio.ensure_future(_reapply_paused_jobs(_scheduler))

    logger.info(
        "Scheduler started (tz=%s). NVD every %dh; KEV every %dm; EPSS every %dh; "
        "MITRE+ATLAS weekly Sunday %02d:%02d; Exploit sources every %dh; "
        "Correlation nightly %02d:%02d IST; OTX nightly %02d:%02d IST; "
        "Vulnrichment every %dh; cvelistV5 every %dm; backup every %dh (dead-man check every %dh).",
        tz_name,
        intervals["nvd_hours"],
        intervals["kev_minutes"],
        intervals["epss_hours"],
        mitre_hour,
        mitre_minute,
        exploit_hours if exploit_sources_enabled() else 0,
        corr_hour,
        corr_minute,
        otx_hour,
        otx_minute,
        vulnrichment_hours,
        cvelist_minutes,
        backup_hours,
        max(1, backup_hours // 2),
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    _scheduler = None
