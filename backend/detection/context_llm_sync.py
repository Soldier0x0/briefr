"""Scheduler-side LLM enrichment of DetectionContext artifacts (Track K4)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import aiosqlite

from ai.llm_router import any_llm_provider_configured
from database import read_cve_exploits_from_db, set_feed_cache
from detection.artifact_extract import build_extraction_text, extract_artifacts_via_llm
from detection.context import (
    build_detection_context,
    get_detection_context,
    set_detection_context,
    _parse_cwe_ids,
)
from ttl_constants import HOURS_PER_YEAR

logger = logging.getLogger(__name__)

LLM_CACHE_PREFIX = "detection_ctx_llm:"
RETRY_HOURS = 168.0


def detection_context_llm_enabled() -> bool:
    flag = os.environ.get("DETECTION_CONTEXT_LLM_ENABLED", "0").strip().lower()
    return flag in ("1", "true", "yes") and any_llm_provider_configured()


def get_detection_context_llm_max_per_run() -> int:
    try:
        return int(os.environ.get("DETECTION_CONTEXT_LLM_MAX_PER_RUN", "10"))
    except ValueError:
        return 10


def get_detection_context_llm_retry_hours() -> float:
    try:
        return float(os.environ.get("DETECTION_CONTEXT_LLM_RETRY_HOURS", str(RETRY_HOURS)))
    except ValueError:
        return RETRY_HOURS


async def get_cves_for_detection_context_llm(
    db: aiosqlite.Connection,
    limit: int,
    *,
    retry_hours: float = RETRY_HOURS,
) -> list[dict]:
    """CVEs with exploit rows, has_poc, and no recent LLM extraction cache entry."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=retry_hours)
    ).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.description, c.affected_products, c.cwe_ids, c.mitre_technique
        FROM cves c
        WHERE COALESCE(c.has_poc, 0) = 1
          AND EXISTS (
            SELECT 1 FROM cve_exploits ce WHERE ce.cve_id = c.cve_id
          )
          AND NOT EXISTS (
            SELECT 1 FROM feed_cache fc
            WHERE fc.cache_key = 'detection_ctx_llm:' || c.cve_id
              AND fc.cached_at > ?
          )
        ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
        LIMIT ?
        """,
        (cutoff, limit),
    )
    return [dict(row) for row in rows]


def _apply_artifacts_to_context(
    base_ctx: dict,
    artifacts: list[dict],
    *,
    provider: str,
    model: str,
) -> dict:
    ctx = dict(base_ctx)
    ctx["artifacts"] = artifacts
    ctx["provider"] = provider
    ctx["model"] = model
    return ctx


async def run_detection_context_llm_sync(
    db: aiosqlite.Connection | None = None,
    progress_cb=None,
) -> dict:
    """Scheduler job: LLM-extract artifacts into DetectionContext cache."""
    from ai.llm_session import llm_job_session
    from database import get_db

    stats = {"candidates": 0, "extracted": 0, "written": 0, "errors": 0, "skipped": 0}
    retry_hours = get_detection_context_llm_retry_hours()
    limit = get_detection_context_llm_max_per_run()

    async def _load_candidates(conn):
        return await get_cves_for_detection_context_llm(
            conn, limit=limit, retry_hours=retry_hours
        )

    if db is not None:
        candidates = await _load_candidates(db)
    else:
        conn = await get_db()
        try:
            candidates = await _load_candidates(conn)
        finally:
            await conn.close()

    stats["candidates"] = len(candidates)
    if not candidates:
        return stats

    with llm_job_session():
        for index, row in enumerate(candidates):
            cve_id = row["cve_id"]
            if progress_cb:
                progress_cb(
                    f"DetectionContext LLM: {index + 1}/{stats['candidates']} ({cve_id})"
                )

            async def _read_exploits(conn, _cve_id=cve_id):
                return await read_cve_exploits_from_db(
                    conn, _cve_id, max_age_hours=HOURS_PER_YEAR
                )

            if db is not None:
                exploits = await _read_exploits(db)
            else:
                conn = await get_db()
                try:
                    exploits = await _read_exploits(conn)
                finally:
                    await conn.close()

            if not exploits:
                stats["skipped"] += 1
                continue

            try:
                source_text = await build_extraction_text(
                    description=row.get("description") or "",
                    exploits=exploits,
                )
            except Exception as exc:
                stats["errors"] += 1
                logger.error("DetectionContext LLM source build failed for %s: %s", cve_id, exc)
                continue

            if len(source_text) < 40:
                stats["skipped"] += 1

                async def _cache_skip(conn, _cve_id=cve_id):
                    await set_feed_cache(
                        conn,
                        f"{LLM_CACHE_PREFIX}{_cve_id.upper()}",
                        {"artifacts": [], "provider": "", "model": "", "skipped": "short_text"},
                    )
                    await conn.commit()

                if db is not None:
                    await _cache_skip(db)
                else:
                    conn = await get_db()
                    try:
                        await _cache_skip(conn)
                    finally:
                        await conn.close()
                continue

            try:
                def _provider_progress(provider: str, _idx=index, _total=stats["candidates"], _cve=cve_id):
                    if progress_cb:
                        progress_cb(
                            f"DetectionContext LLM: {_idx + 1}/{_total} ({_cve}) — {provider}…"
                        )

                result = await extract_artifacts_via_llm(
                    source_text,
                    on_provider_attempt=_provider_progress,
                )
            except Exception as exc:
                stats["errors"] += 1
                logger.error("DetectionContext LLM extract failed for %s: %s", cve_id, exc)
                continue

            if result is None:
                stats["errors"] += 1
                logger.warning(
                    "DetectionContext LLM: all providers failed for %s (%d/%d)",
                    cve_id,
                    index + 1,
                    stats["candidates"],
                )
                continue

            artifacts, completion = result
            if artifacts:
                stats["extracted"] += 1

            async def _persist(
                conn,
                _cve_id=cve_id,
                _row=row,
                _artifacts=artifacts,
                _completion=completion,
            ):
                nonlocal stats
                existing = await get_detection_context(conn, _cve_id)
                if existing:
                    base_ctx = existing
                else:
                    base_ctx = build_detection_context(
                        cve_id=_cve_id,
                        cwe_ids=_parse_cwe_ids(_row.get("cwe_ids")),
                        technique_id=_row.get("mitre_technique") or "",
                        affected_products=_row.get("affected_products"),
                    )
                enriched = _apply_artifacts_to_context(
                    base_ctx,
                    _artifacts,
                    provider=_completion.provider,
                    model=_completion.model,
                )
                await set_detection_context(conn, _cve_id, enriched)
                stats["written"] += 1
                await set_feed_cache(
                    conn,
                    f"{LLM_CACHE_PREFIX}{_cve_id.upper()}",
                    {
                        "artifacts": _artifacts,
                        "provider": _completion.provider,
                        "model": _completion.model,
                    },
                )
                await conn.commit()

            if db is not None:
                await _persist(db)
            else:
                conn = await get_db()
                try:
                    await _persist(conn)
                finally:
                    await conn.close()

    return stats
