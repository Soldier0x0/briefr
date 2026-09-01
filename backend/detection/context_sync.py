"""Scheduler-side DetectionContext backfill (Sprint D2).

Populates ``feed_cache`` keys ``detection_ctx:{cve_id}`` from CVE row
metadata. Disabled by default; never runs on the request path.
"""

from __future__ import annotations

import logging
import os

from db.types import DbConnection

from detection.context import (
    DETECTION_CTX_CACHE_HOURS,
    build_detection_context,
    set_detection_context,
    _parse_cwe_ids,
)

logger = logging.getLogger(__name__)


def detection_context_sync_enabled() -> bool:
    return os.environ.get("DETECTION_CONTEXT_SYNC_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_detection_context_max_per_run() -> int:
    try:
        return int(os.environ.get("DETECTION_CONTEXT_SYNC_MAX_PER_RUN", "500"))
    except ValueError:
        return 500


async def get_cves_for_detection_context_sync(
    db: DbConnection,
    limit: int,
) -> list[dict]:
    """CVEs missing a fresh detection_ctx cache entry."""
    rows = await db.execute_fetchall(
        """
        SELECT c.cve_id, c.affected_products, c.cwe_ids, c.mitre_technique
        FROM cves c
        LEFT JOIN feed_cache fc
          ON fc.cache_key = 'detection_ctx:' || c.cve_id
         AND fc.cached_at > datetime('now', ?)
        WHERE fc.cache_key IS NULL
        ORDER BY c.is_kev DESC, c.has_poc DESC, c.published DESC
        LIMIT ?
        """,
        (f"-{DETECTION_CTX_CACHE_HOURS} hours", limit),
    )
    return [dict(row) for row in rows]


async def run_detection_context_sync(
    db: DbConnection | None = None,
    progress_cb=None,
) -> dict:
    """Backfill DetectionContext cache rows for CVEs missing them."""
    from database import get_db

    owned = db is None
    if owned:
        db = await get_db()

    limit = get_detection_context_max_per_run()
    try:
        candidates = await get_cves_for_detection_context_sync(db, limit)
        if not candidates:
            return {"candidates": 0, "written": 0}

        written = 0
        for idx, row in enumerate(candidates, start=1):
            cve_id = row["cve_id"]
            cwe_ids = _parse_cwe_ids(row.get("cwe_ids"))
            ctx = build_detection_context(
                cve_id=cve_id,
                cwe_ids=cwe_ids,
                technique_id=row.get("mitre_technique") or "",
                affected_products=row.get("affected_products"),
            )
            await set_detection_context(db, cve_id, ctx)
            written += 1
            if progress_cb and idx % 25 == 0:
                progress_cb(f"DetectionContext: {idx}/{len(candidates)} written")

        if owned:
            await db.commit()
        return {"candidates": len(candidates), "written": written}
    finally:
        if owned:
            await db.close()
