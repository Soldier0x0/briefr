"""Scheduler-side LLM enrichment of DetectionContext artifacts (Track K4)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from db.types import DbConnection

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
    db: DbConnection,
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
    db: DbConnection,
    progress_cb=None,
) -> dict:
    """Scheduler job: LLM-extract artifacts into DetectionContext cache."""
    from ai.llm_session import llm_job_session

    stats = {"candidates": 0, "extracted": 0, "written": 0, "errors": 0, "skipped": 0}
    retry_hours = get_detection_context_llm_retry_hours()
    limit = get_detection_context_llm_max_per_run()

    candidates = await get_cves_for_detection_context_llm(
        db, limit=limit, retry_hours=retry_hours
    )

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

            exploits = await read_cve_exploits_from_db(
                db, cve_id, max_age_hours=HOURS_PER_YEAR
            )

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
                await set_feed_cache(
                    db,
                    f"{LLM_CACHE_PREFIX}{cve_id.upper()}",
                    {"artifacts": [], "provider": "", "model": "", "skipped": "short_text"},
                )
                await db.commit()
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

            existing = await get_detection_context(db, cve_id)
            if existing:
                base_ctx = existing
            else:
                base_ctx = build_detection_context(
                    cve_id=cve_id,
                    cwe_ids=_parse_cwe_ids(row.get("cwe_ids")),
                    technique_id=row.get("mitre_technique") or "",
                    affected_products=row.get("affected_products"),
                )
            enriched = _apply_artifacts_to_context(
                base_ctx,
                artifacts,
                provider=completion.provider,
                model=completion.model,
            )
            await set_detection_context(db, cve_id, enriched)
            stats["written"] += 1
            await set_feed_cache(
                db,
                f"{LLM_CACHE_PREFIX}{cve_id.upper()}",
                {
                    "artifacts": artifacts,
                    "provider": completion.provider,
                    "model": completion.model,
                },
            )
            await db.commit()

    return stats
