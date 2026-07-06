import asyncio

# Keys must match the `id=` strings passed to scheduler.add_job() exactly.
# incident_feed_refresh, backup_deadman_check, and session_cleanup have no
# entry here — they run without a lock today (verified against
# scheduler.py's add_job() calls and routers/admin.py's prior _JOB_LOCK_MAP;
# this module only consolidates locks that already existed, it doesn't add
# new ones).
_LOCKS: dict[str, asyncio.Lock] = {
    "nvd_incremental_sync": asyncio.Lock(),
    "kev_metadata_sync": asyncio.Lock(),
    "epss_score_sync": asyncio.Lock(),
    "weekly_mitre_refresh": asyncio.Lock(),
    "atlas_version_check": asyncio.Lock(),
    "otx_nightly_correlation": asyncio.Lock(),
    "otx_continuous_sync": asyncio.Lock(),
    "nightly_correlation": asyncio.Lock(),
    "vulnrichment_snapshot_sync": asyncio.Lock(),
    "cvelistv5_incremental_sync": asyncio.Lock(),
    "embeddings_backfill": asyncio.Lock(),
    "llm_product_extraction": asyncio.Lock(),
    "exploit_sources_sync": asyncio.Lock(),
    "scheduled_backup": asyncio.Lock(),
    # _epss_backfill_lock has no corresponding job ID — stays a private var
    # in scheduler.py.
}


def get_lock(job_id: str) -> asyncio.Lock | None:
    return _LOCKS.get(job_id)


def any_locked() -> bool:
    return any(l.locked() for l in _LOCKS.values())


def locked_jobs() -> list[str]:
    return [job_id for job_id, l in _LOCKS.items() if l.locked()]
