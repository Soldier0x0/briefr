import asyncio

# Keys must match the `id=` strings passed to scheduler.add_job() exactly.
# incident_feed_refresh, backup_deadman_check, session_cleanup,
# cache_retention_cleanup, watchlist_monitor_alerts, and api_key_health_check
# have no entry here — they run without a lock today (each job is registered
# with max_instances=1, so APScheduler itself prevents overlap; this module
# only consolidates locks that already existed, it doesn't add new ones).
_LOCKS: dict[str, asyncio.Lock] = {
    "nvd_incremental_sync": asyncio.Lock(),
    "kev_metadata_sync": asyncio.Lock(),
    "kev_backlog_reconcile": asyncio.Lock(),
    "threatfox_sync": asyncio.Lock(),
    "urlhaus_sync": asyncio.Lock(),
    "malwarebazaar_sync": asyncio.Lock(),
    "vulncheck_kev_sync": asyncio.Lock(),
    "ioc_retro_match": asyncio.Lock(),
    "epss_score_sync": asyncio.Lock(),
    "weekly_mitre_refresh": asyncio.Lock(),
    "atlas_version_check": asyncio.Lock(),
    "otx_nightly_correlation": asyncio.Lock(),
    "otx_continuous_sync": asyncio.Lock(),
    "nightly_correlation": asyncio.Lock(),
    "vulnrichment_snapshot_sync": asyncio.Lock(),
    "cvelistv5_incremental_sync": asyncio.Lock(),
    "embeddings_backfill": asyncio.Lock(),
    "catchup_tick": asyncio.Lock(),
    "llm_product_extraction": asyncio.Lock(),
    "detection_context_sync": asyncio.Lock(),
    "detection_context_llm": asyncio.Lock(),
    "sigmahq_index_sync": asyncio.Lock(),
    "exploit_sources_sync": asyncio.Lock(),
    "scheduled_backup": asyncio.Lock(),
    "resource_metrics_sample": asyncio.Lock(),
    "cpe_catalog_sync": asyncio.Lock(),
    "publication_source_sync": asyncio.Lock(),
    # _epss_backfill_lock has no corresponding job ID — stays a private var
    # in scheduler.py.
}


def get_lock(job_id: str) -> asyncio.Lock | None:
    return _LOCKS.get(job_id)


def any_locked() -> bool:
    return any(l.locked() for l in _LOCKS.values())


def locked_jobs() -> list[str]:
    return [job_id for job_id, l in _LOCKS.items() if l.locked()]
