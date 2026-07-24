"""Admin retrieval / embeddings index health (post-E8 ops honesty).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import logging
from typing import Any

from db.embeddings_store import (
    count_embeddings_by_entity,
    count_embeddings_pending_missing,
    embeddings_pgvector_writes_enabled,
)
from db.types import DbConnection
from ml.embeddings import (
    embeddings_auto_on_ingest_enabled,
    embeddings_enabled,
    get_embeddings_model_name,
)

logger = logging.getLogger(__name__)

INGEST_TAIL_SYNC_KEY = "embeddings.ingest_tail.last"


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def _extension_vector_status(db: DbConnection) -> str:
    if not _is_postgres_connection(db):
        return "n/a"
    try:
        rows = await db.execute_fetchall(
            "SELECT 1 AS ok FROM pg_extension WHERE extname = 'vector'"
        )
        return "present" if rows else "absent"
    except Exception:
        logger.exception("pg_extension probe failed")
        return "absent"


async def _last_backfill_summary(db: DbConnection) -> dict[str, Any]:
    """Read scheduler.last_run.embeddings_backfill from sync_state if present."""
    empty = {
        "last_run_utc": None,
        "records_upserted": None,
        "had_error": None,
        "error_message": None,
    }
    try:
        from db.sync_state import get_sync_state_value

        raw = await get_sync_state_value(db, "scheduler.last_run.embeddings_backfill")
    except Exception:
        logger.exception("last_backfill sync_state read failed")
        return empty
    if not raw:
        return empty
    try:
        history = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return empty
    if not isinstance(history, list) or not history:
        return empty
    latest = history[0] if isinstance(history[0], dict) else {}
    return {
        "last_run_utc": latest.get("last_run_utc") or latest.get("started_at"),
        "records_upserted": latest.get("records_upserted"),
        "had_error": latest.get("had_error"),
        "error_message": latest.get("error_message"),
    }


async def _last_ingest_tail_summary(db: DbConnection) -> dict[str, Any]:
    empty = {
        "last_run_utc": None,
        "embedded": None,
        "had_error": None,
        "error_message": None,
    }
    try:
        from db.sync_state import get_sync_state_value

        raw = await get_sync_state_value(db, INGEST_TAIL_SYNC_KEY)
    except Exception:
        logger.exception("ingest_tail sync_state read failed")
        return empty
    if not raw:
        return empty
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        "last_run_utc": data.get("last_run_utc"),
        "embedded": data.get("embedded"),
        "had_error": data.get("had_error"),
        "error_message": data.get("error_message"),
    }


def _degraded_reason(
    *,
    enabled: bool,
    extension_vector: str,
    total: int,
) -> dict[str, str] | None:
    if not enabled:
        return {"reason": "disabled"}
    if extension_vector == "absent":
        return {"reason": "no_vector_extension"}
    if total == 0:
        return {"reason": "cold_index"}
    return None


async def build_retrieval_health(db: DbConnection) -> dict[str, Any]:
    model = get_embeddings_model_name()
    enabled = embeddings_enabled()
    auto = embeddings_auto_on_ingest_enabled()
    pgvector_writes = embeddings_pgvector_writes_enabled()
    extension_vector = await _extension_vector_status(db)
    counts = await count_embeddings_by_entity(db, model)
    pending_raw = await count_embeddings_pending_missing(db, model)
    pending = {
        "cve": int(pending_raw.get("cve") or 0),
        "technique": int(pending_raw.get("technique") or 0),
        "campaign": int(pending_raw.get("campaign") or 0),
        "includes_hash_drift": False,
        "note": "missing_or_migrated_only",
    }
    last_backfill = await _last_backfill_summary(db)
    last_ingest_tail = await _last_ingest_tail_summary(db)
    degraded = _degraded_reason(
        enabled=enabled,
        extension_vector=extension_vector,
        total=int(counts.get("total") or 0),
    )
    return {
        "embeddings_enabled": enabled,
        "auto_on_ingest": auto,
        "pgvector_writes": pgvector_writes,
        "model": model,
        "extension_vector": extension_vector,
        "counts": counts,
        "pending": pending,
        "last_backfill": last_backfill,
        "last_ingest_tail": last_ingest_tail,
        "degraded": degraded,
    }
