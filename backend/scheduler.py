import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
from feeds.atlas import refresh_atlas_data
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
from webhooks.alerts import check_backup_deadman, get_backup_interval_hours, process_kev_stack_alerts
from backup.manager import run_backup

logger = logging.getLogger(__name__)

SCHEDULER_REFRESH_TZ = "Asia/Kolkata"

_scheduler: AsyncIOScheduler | None = None
_nvd_lock = asyncio.Lock()
_kev_lock = asyncio.Lock()
_epss_lock = asyncio.Lock()
_epss_backfill_lock = asyncio.Lock()
_mitre_refresh_lock = asyncio.Lock()
_otx_lock = asyncio.Lock()
_correlation_lock = asyncio.Lock()
_vulnrichment_lock = asyncio.Lock()
_cvelistv5_lock = asyncio.Lock()
_embeddings_lock = asyncio.Lock()
_llm_extraction_lock = asyncio.Lock()
_exploit_sources_lock = asyncio.Lock()
_scheduled_backup_lock = asyncio.Lock()


def any_ingest_lock_held() -> bool:
    """True when any ingest-related lock is held (used by /api/admin/system)."""
    return any(lock.locked() for lock in [
        _nvd_lock, _kev_lock, _epss_lock, _epss_backfill_lock,
        _mitre_refresh_lock, _otx_lock, _correlation_lock,
        _vulnrichment_lock, _cvelistv5_lock, _embeddings_lock,
        _llm_extraction_lock, _exploit_sources_lock, _scheduled_backup_lock,
    ])


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

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with _nvd_lock:
            await _run_nvd_incremental_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
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
                stripped = await strip_auto_generated_summaries(db, updated_ids)
                filled = await backfill_display_fields(db, updated_ids)
                poc_marked = await backfill_has_poc(db, updated_ids)
            else:
                stripped = filled = poc_marked = 0
            if updated_ids:
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
    if _kev_lock.locked():
        logger.warning("KEV sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with _kev_lock:
            await _run_kev_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
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
            kev_summaries = await enrich_kev_summaries(db)
            await db.commit()
            if kev_summaries:
                logger.info("Enriched %d KEV summaries from CISA descriptions", kev_summaries)
        finally:
            await db.close()

        if newly_kev:
            try:
                alerted = await process_kev_stack_alerts(newly_kev)
                if alerted:
                    logger.info("KEV-on-stack alerts sent: %d", alerted)
            except Exception as exc:
                logger.error("KEV-on-stack alert processing failed: %s", exc)

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

    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    try:
        async with _epss_lock:
            await _run_epss_sync()
    except Exception as _exc:
        _had_error = True
        _error_msg = str(_exc)[:500]
        raise
    finally:
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
        await _run_epss_backfill()
    return True


async def _run_epss_backfill() -> None:
    start = datetime.now(timezone.utc)
    logger.info("EPSS history backfill started at %s", start.isoformat())

    total_rows = 0
    batch_num = 0
    total_batches = 0
    all_cve_ids: list[str] = []

    db = await get_db()
    try:
        done = await get_sync_state_value(db, EPSS_BACKFILL_DONE_KEY)
        if done:
            logger.info("EPSS backfill: marker %r already set — skipping", EPSS_BACKFILL_DONE_KEY)
            return

        all_cve_ids = await get_all_cve_ids(db)
        if not all_cve_ids:
            logger.info("EPSS backfill: DB has no CVEs — marking done immediately")
            await set_sync_state_value(db, EPSS_BACKFILL_DONE_KEY, "1")
            await db.commit()
            return

        total_batches = (len(all_cve_ids) + BACKFILL_BATCH_SIZE - 1) // BACKFILL_BATCH_SIZE
        logger.info(
            "EPSS backfill: %d CVEs → %d batches (size=%d, throttle=%.1fs)",
            len(all_cve_ids),
            total_batches,
            BACKFILL_BATCH_SIZE,
            BACKFILL_THROTTLE_SECONDS,
        )

        for offset in range(0, len(all_cve_ids), BACKFILL_BATCH_SIZE):
            batch = all_cve_ids[offset : offset + BACKFILL_BATCH_SIZE]
            rows = await fetch_epss_time_series_batch(batch)
            if rows:
                inserted = await insert_epss_history_rows(db, rows)
                await db.commit()
                total_rows += inserted

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

        await set_sync_state_value(db, EPSS_BACKFILL_DONE_KEY, "1")
        await db.commit()

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
    finally:
        await db.close()


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

    _start = datetime.now(timezone.utc)
    async with _mitre_refresh_lock:
        start = _start
        logger.info("Weekly MITRE ATT&CK + ATLAS refresh started at %s", start.isoformat())
        ok = True
        try:
            db = await get_db()
            try:
                stats = await refresh_mitre_data(db)
                atlas_stats = await refresh_atlas_data(db)
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
            _mitre_error_msg = str(exc)[:500]
        else:
            _mitre_error_msg = ""
        await _write_job_last_run("weekly_mitre_refresh", _start, had_error=not ok, error_message=_mitre_error_msg)
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
    asyncio.create_task(run_epss_backfill())
    if count >= 10 and exploit_sources_enabled():
        asyncio.create_task(run_exploit_sources_sync())


async def run_exploit_sources_sync() -> bool:
    """Daily exploit-availability feeds: PoC-in-GitHub, ExploitDB, Metasploit, Nuclei."""
    if not exploit_sources_enabled():
        logger.info("Exploit sources sync disabled (EXPLOIT_SOURCES_SYNC_ENABLED=0)")
        return False

    if _exploit_sources_lock.locked():
        logger.warning("Exploit sources sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _exploit_sources_lock:
        start = _start
        logger.info("Exploit sources sync started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                stats = await sync_all_exploit_sources(db)
                await db.commit()
            finally:
                await db.close()
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
            _exploit_error_msg = str(exc)[:500]
        else:
            _exploit_error_msg = ""
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Exploit sources sync finished in %.1fs", duration)
    await _write_job_last_run("exploit_sources_sync", _start, had_error=_had_error, error_message=_exploit_error_msg)
    return True


async def run_vulnrichment_sync() -> bool:
    if _vulnrichment_lock.locked():
        logger.warning("Vulnrichment sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _vulnrichment_lock:
        start = _start
        logger.info("Vulnrichment snapshot sync started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                gap_ids = await get_cves_needing_intel_enrichment(db, limit=1000)
            finally:
                await db.close()

            target = set(gap_ids) if gap_ids else None
            enrichments = await fetch_vulnrichment_enrichments(target)
            if not enrichments:
                logger.info("Vulnrichment sync: no enrichments to apply")
                await _write_job_last_run("vulnrichment_snapshot_sync", _start)
                return True

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
            _vuln_error_msg = str(exc)[:500]
        else:
            _vuln_error_msg = ""
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Vulnrichment snapshot sync finished in %.1fs", duration)
    await _write_job_last_run("vulnrichment_snapshot_sync", _start, had_error=_had_error, error_message=_vuln_error_msg)
    return True


async def run_cvelistv5_sync() -> bool:
    if _cvelistv5_lock.locked():
        logger.warning("cvelistV5 sync already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _cvelistv5_lock:
        start = _start
        logger.info("cvelistV5 incremental sync started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                watermark = await get_sync_state_value(db, CVELISTV5_SYNC_STATE_KEY)
            finally:
                await db.close()

            records, rejected_ids, new_head, advance = await fetch_cvelistv5_delta(watermark)
            if not advance or not new_head:
                await _write_job_last_run("cvelistv5_incremental_sync", _start)
                return True

            applied = 0
            purged = 0
            db = await get_db()
            try:
                if records:
                    applied = await apply_additive_cve_enrichments(db, records)
                if rejected_ids:
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
            _cvelist_error_msg = str(exc)[:500]
        else:
            _cvelist_error_msg = ""
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
        _incident_error_msg = str(exc)[:500]
    else:
        _incident_error_msg = ""
    await _write_job_last_run("incident_feed_refresh", _start, had_error=_had_error, error_message=_incident_error_msg)
    return True


async def run_nightly_correlation() -> bool:
    """Nightly correlation engine: infrastructure, actor, and temporal analysis."""
    if _correlation_lock.locked():
        logger.warning("Correlation job already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _correlation_lock:
        from correlation.engine import (
            prefetch_pulse_iocs_for_nightly,
            run_nightly_correlation as _run_correlation,
        )

        api_key = os.environ.get("OTX_API_KEY", "")
        db = await get_db()
        try:
            # Pre-warm IOC data for Level 1 before running correlation
            if api_key:
                ioc_count = await prefetch_pulse_iocs_for_nightly(db, api_key)
                if ioc_count:
                    await db.commit()
                    logger.info("Pre-fetched IOCs for %d pulses", ioc_count)

            stats = await _run_correlation(db)
            logger.info(
                "Nightly correlation: %d CVEs, %d infra pairs, %d actors, %d anomalies",
                stats.get("cves_processed", 0),
                stats.get("infrastructure_pairs", 0),
                stats.get("actor_findings", 0),
                stats.get("temporal_anomalies", 0),
            )
        except Exception as exc:
            logger.error("Nightly correlation job failed: %s", exc)
            _had_error = True
            _corr_error_msg = str(exc)[:500]
        else:
            _corr_error_msg = ""
        finally:
            await db.close()
    await _write_job_last_run("nightly_correlation", _start, had_error=_had_error, error_message=_corr_error_msg)
    return True


async def run_otx_nightly_sync() -> bool:
    if _otx_lock.locked():
        logger.warning("OTX nightly correlation already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _otx_lock:
        api_key = os.environ.get("OTX_API_KEY", "")
        if not api_key:
            logger.info("OTX_API_KEY not set — skipping nightly correlation")
            await _write_job_last_run("otx_nightly_correlation", _start)
            return False
        db = await get_db()
        try:
            from feeds.otx import run_otx_nightly_correlation

            stats = await run_otx_nightly_correlation(db, api_key)
            await db.commit()
            logger.info(
                "OTX nightly correlation complete: %d CVEs, %d pulses cached",
                stats.get("cves", 0),
                stats.get("pulses", 0),
            )
        except Exception as exc:
            logger.error("OTX nightly correlation failed: %s", exc)
            _had_error = True
            _otx_error_msg = str(exc)[:500]
        else:
            _otx_error_msg = ""
        finally:
            await db.close()
    await _write_job_last_run("otx_nightly_correlation", _start, had_error=_had_error, error_message=_otx_error_msg)
    return True


async def run_embeddings_sync() -> bool:
    """Embed CVE descriptions missing vectors (V1.3 Theme 7).

    No-op unless EMBEDDINGS_ENABLED=1 — the env gate is checked at run time
    so the operator can toggle without re-registering jobs. CPU-only model
    inference happens here (scheduler-side), never on the request path.
    """
    if not embeddings_enabled():
        return False
    if _embeddings_lock.locked():
        logger.info("Embeddings backfill already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _embeddings_lock:
        start = _start
        logger.info("Embeddings backfill started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                stats = await run_embeddings_backfill(db)
            finally:
                await db.close()
            logger.info(
                "Embeddings backfill complete: %d CVEs embedded (model=%s) in %.1fs",
                stats.get("embedded", 0),
                stats.get("model", ""),
                (datetime.now(timezone.utc) - start).total_seconds(),
            )
        except Exception as exc:
            logger.error("Embeddings backfill failed: %s", exc)
            _had_error = True
            _emb_error_msg = str(exc)[:500]
        else:
            _emb_error_msg = ""
    await _write_job_last_run("embeddings_backfill", _start, had_error=_had_error, error_message=_emb_error_msg)
    return True


async def run_llm_extraction_sync() -> bool:
    """LLM product extraction for NVD-unanalyzed CVEs (V1.3 Theme 7).

    No-op unless LLM_PRODUCT_EXTRACTION_ENABLED=1 AND GROQ_API_KEY is set.
    """
    if not llm_product_extraction_enabled():
        return False
    if _llm_extraction_lock.locked():
        logger.info("LLM product extraction already in progress — skipping")
        return False

    _start = datetime.now(timezone.utc)
    _had_error = False
    async with _llm_extraction_lock:
        start = _start
        logger.info("LLM product extraction started at %s", start.isoformat())
        try:
            db = await get_db()
            try:
                stats = await run_llm_product_extraction(db)
            finally:
                await db.close()
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
            _llm_error_msg = str(exc)[:500]
        else:
            _llm_error_msg = ""
    await _write_job_last_run("llm_product_extraction", _start, had_error=_had_error, error_message=_llm_error_msg)
    return True


async def run_scheduled_backup() -> bool:
    """Scheduler hook: create a backup archive and prune old ones, on
    BACKUP_INTERVAL_HOURS. run_backup() itself no-ops when BACKUP_ENABLED=0
    and applies BACKUP_RETENTION_COUNT pruning — this just wires it to a job."""
    if _scheduled_backup_lock.locked():
        logger.info("Scheduled backup already in progress — skipping")
        return False
    _start = datetime.now(timezone.utc)
    _had_error = False
    _error_msg = ""
    async with _scheduled_backup_lock:
        try:
            await asyncio.to_thread(run_backup, reason="scheduled")
        except Exception as exc:
            logger.error("Scheduled backup failed: %s", exc)
            _had_error = True
            _error_msg = str(exc)[:500]
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
        _deadman_error_msg = str(exc)[:500]
        return False
    finally:
        await _write_job_last_run("backup_deadman_check", _start, had_error=_had_error, error_message=_deadman_error_msg)


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

    backup_hours = get_backup_interval_hours()
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
