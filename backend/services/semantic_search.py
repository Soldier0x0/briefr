"""Hybrid / semantic CVE search orchestration (E3).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import logging
from typing import Any

from db.embeddings_search import (
    SearchMode,
    ann_search_by_query_vector,
    build_hybrid_results,
    classify_query_shape,
    find_similar_via_embeddings_table,
    keyword_search_cves,
)
from db.embeddings_pgvector import DEFAULT_EMBEDDING_DIMS
from db.types import DbConnection
from ml.embeddings import (
    embed_query_text,
    embeddings_enabled,
    get_embeddings_model_name,
)

logger = logging.getLogger(__name__)

_MAX_LIMIT = 50
_DEFAULT_LIMIT = 20


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def _hydrate_cve_cards(db: DbConnection, cve_ids: list[str]) -> dict[str, dict]:
    """Card fields for search hits (keyword rows already include these)."""
    normalized = [c.upper() for c in cve_ids if c]
    if not normalized:
        return {}
    pg = _is_postgres_connection(db)
    out: dict[str, dict] = {}
    chunk = 400
    for i in range(0, len(normalized), chunk):
        part = normalized[i : i + chunk]
        if pg:
            placeholders = ", ".join(f"${j}" for j in range(1, len(part) + 1))
        else:
            placeholders = ", ".join("?" for _ in part)
        rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, description, summary, cvss_score, severity,
                   published, epss_score, is_kev
            FROM cves WHERE cve_id IN ({placeholders})
            """,
            tuple(part),
        )
        for row in rows:
            out[row["cve_id"]] = dict(row)
    return out


async def run_semantic_search(
    db,
    q: str,
    *,
    mode: SearchMode = "hybrid",
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Run keyword / semantic / hybrid search with honest ``meta.method``."""
    text = (q or "").strip()
    if not text:
        return {
            "data": [],
            "meta": {
                "method": "keyword",
                "mode_requested": mode,
                "query_shape": "short",
                "q": "",
            },
        }

    capped = max(1, min(int(limit), _MAX_LIMIT))
    shape = classify_query_shape(text)
    mode_norm: SearchMode = (
        mode if mode in ("hybrid", "keyword", "semantic") else "hybrid"
    )

    keyword_rows = await keyword_search_cves(db, text, limit=capped)
    vector_hits: list[dict] = []

    need_vector = False
    if mode_norm == "semantic":
        need_vector = True
    elif mode_norm == "hybrid" and shape != "cve_id":
        need_vector = True

    if need_vector and embeddings_enabled():
        if shape == "cve_id":
            # Use the CVE's stored vector as the query — no model inference.
            try:
                similar = await find_similar_via_embeddings_table(
                    db, text.upper(), get_embeddings_model_name(), limit=capped
                )
            except Exception:
                logger.exception("CVE-id semantic neighbor lookup failed")
                similar = None
            if similar:
                vector_hits = similar
        else:
            query_blob = await embed_query_text(text)
            if query_blob is not None:
                dims = len(query_blob) // 4
                try:
                    vector_hits = await ann_search_by_query_vector(
                        db,
                        get_embeddings_model_name(),
                        query_blob,
                        limit=capped,
                        expected_dim=dims or DEFAULT_EMBEDDING_DIMS,
                    )
                except Exception:
                    logger.exception("vector ANN search failed — keyword only")
                    vector_hits = []

    ids = list(
        dict.fromkeys(
            [r["cve_id"] for r in keyword_rows]
            + [h["cve_id"] for h in vector_hits]
        )
    )
    cards = await _hydrate_cve_cards(db, ids)
    # Prefer keyword row fields when present (same columns).
    for row in keyword_rows:
        cards[row["cve_id"]] = row

    results, method = build_hybrid_results(
        keyword_rows=keyword_rows,
        vector_hits=vector_hits,
        cards_by_id=cards,
        limit=capped,
        query_shape=shape,
        mode=mode_norm,
    )
    return {
        "data": results,
        "meta": {
            "method": method,
            "mode_requested": mode_norm,
            "query_shape": shape,
            "q": text[:200],
            "embeddings_enabled": embeddings_enabled(),
        },
    }
