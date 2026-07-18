"""pgvector ANN + keyword helpers for related CVEs and hybrid search (E3).

Related uses stored vectors only (no request-path inference). Semantic search
embeds the query once when ``EMBEDDINGS_ENABLED=1`` (design §7.1); bulk ML
sweeps remain scheduler-only.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import re
from typing import Any, Literal

import numpy as np

from db.embeddings_pgvector import (
    DEFAULT_EMBEDDING_DIMS,
    ENTITY_TYPE_CVE,
    blob_to_pgvector_literal,
)
from db.types import DbConnection

QueryShape = Literal["cve_id", "short", "long"]
SearchMode = Literal["hybrid", "keyword", "semantic"]

_CVE_ID_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)
_RRF_K = 60

_ANN_RELATED_PG = """
SELECT e2.entity_id AS cve_id,
       (1.0 - (e2.embedding <=> e1.embedding))::float8 AS similarity
FROM embeddings e1
JOIN embeddings e2
  ON e2.entity_type = e1.entity_type
 AND e2.model = e1.model
 AND e2.entity_id <> e1.entity_id
WHERE e1.entity_type = $1
  AND e1.entity_id = $2
  AND e1.model = $3
ORDER BY e2.embedding <=> e1.embedding
LIMIT $4
"""

_ANN_BY_VECTOR_PG = """
SELECT entity_type, entity_id,
       (1.0 - (embedding <=> CAST($1 AS vector)))::float8 AS similarity
FROM embeddings
WHERE entity_type = ANY($2::text[])
  AND model = $3
ORDER BY embedding <=> CAST($1 AS vector)
LIMIT $4
"""

_KEYWORD_TECH_SQLITE = """
SELECT technique_id, name, description, tactic, url
FROM mitre_techniques
WHERE (
    UPPER(technique_id) = ?
    OR LOWER(technique_id) LIKE ?
    OR LOWER(name) LIKE ?
    OR LOWER(COALESCE(description, '')) LIKE ?
    OR LOWER(COALESCE(tactic, '')) LIKE ?
)
ORDER BY
  CASE WHEN UPPER(technique_id) = ? THEN 0 ELSE 1 END,
  technique_id
LIMIT ?
"""

_KEYWORD_TECH_PG = """
SELECT technique_id, name, description, tactic, url
FROM mitre_techniques
WHERE (
    UPPER(technique_id) = $1
    OR LOWER(technique_id) LIKE $2
    OR LOWER(name) LIKE $3
    OR LOWER(COALESCE(description, '')) LIKE $4
    OR LOWER(COALESCE(tactic, '')) LIKE $5
)
ORDER BY
  CASE WHEN UPPER(technique_id) = $1 THEN 0 ELSE 1 END,
  technique_id
LIMIT $6
"""

_KEYWORD_CAMPAIGN_SQLITE = """
SELECT campaign_id, label, adversary, malware_families, tags,
       lifecycle, member_count, confidence
FROM correlation_campaigns
WHERE retracted_at IS NULL
  AND (
    LOWER(campaign_id) = ?
    OR LOWER(COALESCE(label, '')) LIKE ?
    OR LOWER(COALESCE(adversary, '')) LIKE ?
    OR LOWER(COALESCE(malware_families, '')) LIKE ?
    OR LOWER(COALESCE(tags, '')) LIKE ?
)
ORDER BY
  CASE WHEN LOWER(campaign_id) = ? THEN 0 ELSE 1 END,
  COALESCE(last_seen, computed_at) DESC
LIMIT ?
"""

_KEYWORD_CAMPAIGN_PG = """
SELECT campaign_id, label, adversary, malware_families, tags,
       lifecycle, member_count, confidence
FROM correlation_campaigns
WHERE retracted_at IS NULL
  AND (
    LOWER(campaign_id) = $1
    OR LOWER(COALESCE(label, '')) LIKE $2
    OR LOWER(COALESCE(adversary, '')) LIKE $3
    OR LOWER(COALESCE(malware_families, '')) LIKE $4
    OR LOWER(COALESCE(tags, '')) LIKE $5
)
ORDER BY
  CASE WHEN LOWER(campaign_id) = $1 THEN 0 ELSE 1 END,
  COALESCE(last_seen, computed_at) DESC NULLS LAST
LIMIT $6
"""

_GET_CVE_EMBEDDING_BLOB_SQLITE = """
SELECT embedding FROM embeddings
WHERE entity_type = ? AND entity_id = ? AND model = ?
"""

_GET_ALL_CVE_EMBEDDING_BLOBS_SQLITE = """
SELECT entity_id, embedding FROM embeddings
WHERE entity_type = ? AND model = ? AND entity_id != ?
"""

_KEYWORD_SEARCH_SQLITE = """
SELECT cve_id, description, summary, cvss_score, severity, published, epss_score,
       is_kev
FROM cves
WHERE (
    UPPER(cve_id) = ?
    OR LOWER(cve_id) LIKE ?
    OR LOWER(description) LIKE ?
    OR LOWER(COALESCE(summary, '')) LIKE ?
)
ORDER BY
  CASE WHEN UPPER(cve_id) = ? THEN 0 ELSE 1 END,
  published DESC
LIMIT ?
"""

_KEYWORD_SEARCH_PG = """
SELECT cve_id, description, summary, cvss_score, severity, published, epss_score,
       is_kev
FROM cves
WHERE (
    UPPER(cve_id) = $1
    OR LOWER(cve_id) LIKE $2
    OR LOWER(description) LIKE $3
    OR LOWER(COALESCE(summary, '')) LIKE $4
)
ORDER BY
  CASE WHEN UPPER(cve_id) = $1 THEN 0 ELSE 1 END,
  published DESC
LIMIT $5
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def classify_query_shape(q: str) -> QueryShape:
    text = (q or "").strip()
    if _CVE_ID_RE.match(text):
        return "cve_id"
    tokens = [t for t in re.split(r"\s+", text) if t]
    if len(tokens) <= 2:
        return "short"
    return "long"


def rrf_merge(
    ranked_lists: list[list[str]],
    *,
    k: int = _RRF_K,
    limit: int = 20,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over ordered id lists. Higher score = better."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, entity_id in enumerate(ranked, start=1):
            if not entity_id:
                continue
            scores[entity_id] = scores.get(entity_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:limit]


async def find_similar_via_embeddings_table(
    db: DbConnection,
    cve_id: str,
    model: str,
    *,
    limit: int = 5,
) -> list[dict] | None:
    """Top-k neighbors from ``embeddings``. None if target has no row."""
    cve_key = cve_id.upper()
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            _ANN_RELATED_PG, (ENTITY_TYPE_CVE, cve_key, model, limit)
        )
        if not rows:
            # Distinguish "no neighbors" vs "target missing": probe target.
            probe = await db.execute_fetchall(
                """
                SELECT 1 FROM embeddings
                WHERE entity_type = $1 AND entity_id = $2 AND model = $3
                """,
                (ENTITY_TYPE_CVE, cve_key, model),
            )
            if not probe:
                return None
            return []
        return [
            {
                "cve_id": row["cve_id"],
                "similarity": round(float(row["similarity"]), 4),
            }
            for row in rows
        ]

    target_rows = await db.execute_fetchall(
        _GET_CVE_EMBEDDING_BLOB_SQLITE, (ENTITY_TYPE_CVE, cve_key, model)
    )
    if not target_rows:
        return None
    target_blob = target_rows[0]["embedding"]
    if target_blob is None:
        return None
    target = np.frombuffer(bytes(target_blob), dtype="<f4")
    cand_rows = await db.execute_fetchall(
        _GET_ALL_CVE_EMBEDDING_BLOBS_SQLITE, (ENTITY_TYPE_CVE, model, cve_key)
    )
    pairs = [
        (row["entity_id"], bytes(row["embedding"]))
        for row in cand_rows
        if row["embedding"] is not None
        and len(bytes(row["embedding"])) == target.nbytes
    ]
    if not pairs:
        return []
    ids = [rid for rid, _ in pairs]
    matrix = np.frombuffer(b"".join(blob for _rid, blob in pairs), dtype="<f4")
    matrix = matrix.reshape(len(pairs), target.size)
    similarities = matrix @ target
    k = min(limit, len(ids))
    top = np.argpartition(-similarities, k - 1)[:k]
    top = top[np.argsort(-similarities[top])]
    return [
        {"cve_id": ids[i], "similarity": round(float(similarities[i]), 4)}
        for i in top
    ]


async def ann_search_by_query_vector(
    db: DbConnection,
    model: str,
    query_blob: bytes,
    *,
    limit: int = 20,
    expected_dim: int = DEFAULT_EMBEDDING_DIMS,
    entity_types: list[str] | None = None,
) -> list[dict]:
    """Vector ANN / cosine scan for a query embedding blob."""
    types = entity_types or [ENTITY_TYPE_CVE]
    pg = _is_postgres_connection(db)
    if pg:
        literal = blob_to_pgvector_literal(query_blob, expected_dim=expected_dim)
        if literal is None:
            return []
        rows = await db.execute_fetchall(
            _ANN_BY_VECTOR_PG, (literal, types, model, limit)
        )
        return [
            {
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "cve_id": row["entity_id"] if row["entity_type"] == ENTITY_TYPE_CVE else None,
                "similarity": round(float(row["similarity"]), 4),
            }
            for row in rows
        ]

    query = np.frombuffer(query_blob, dtype="<f4")
    placeholders = ", ".join("?" for _ in types)
    rows = await db.execute_fetchall(
        f"""
        SELECT entity_type, entity_id, embedding FROM embeddings
        WHERE entity_type IN ({placeholders}) AND model = ?
        """,
        (*types, model),
    )
    pairs = [
        (row["entity_type"], row["entity_id"], bytes(row["embedding"]))
        for row in rows
        if row["embedding"] is not None
        and len(bytes(row["embedding"])) == query.nbytes
    ]
    if not pairs:
        return []
    matrix = np.frombuffer(b"".join(blob for _t, _i, blob in pairs), dtype="<f4")
    matrix = matrix.reshape(len(pairs), query.size)
    similarities = matrix @ query
    k = min(limit, len(pairs))
    top = np.argpartition(-similarities, k - 1)[:k]
    top = top[np.argsort(-similarities[top])]
    out = []
    for i in top:
        etype, eid, _blob = pairs[i]
        out.append(
            {
                "entity_type": etype,
                "entity_id": eid,
                "cve_id": eid if etype == ENTITY_TYPE_CVE else None,
                "similarity": round(float(similarities[i]), 4),
            }
        )
    return out


async def keyword_search_techniques(
    db: DbConnection,
    q: str,
    *,
    limit: int = 20,
) -> list[dict]:
    text = (q or "").strip()
    if not text:
        return []
    exact = text.upper()
    like = f"%{text.lower()}%"
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            _KEYWORD_TECH_PG, (exact, like, like, like, like, limit)
        )
    else:
        rows = await db.execute_fetchall(
            _KEYWORD_TECH_SQLITE, (exact, like, like, like, like, exact, limit)
        )
    return [dict(row) for row in rows]


async def keyword_search_campaigns(
    db: DbConnection,
    q: str,
    *,
    limit: int = 20,
) -> list[dict]:
    """Substring match on campaign label / adversary / malware / tags (E8)."""
    text = (q or "").strip()
    if not text:
        return []
    exact = text.lower()
    like = f"%{exact}%"
    capped = max(1, min(int(limit), 50))
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            _KEYWORD_CAMPAIGN_PG, (exact, like, like, like, like, capped)
        )
    else:
        rows = await db.execute_fetchall(
            _KEYWORD_CAMPAIGN_SQLITE, (exact, like, like, like, like, exact, capped)
        )
    return [dict(row) for row in rows]


async def keyword_search_cves(
    db: DbConnection,
    q: str,
    *,
    limit: int = 20,
) -> list[dict]:
    """Substring / exact CVE-id keyword search (works on SQLite + Postgres)."""
    text = (q or "").strip()
    if not text:
        return []
    exact = text.upper() if _CVE_ID_RE.match(text) else text.upper()
    like = f"%{text.lower()}%"
    pg = _is_postgres_connection(db)
    if pg:
        rows = await db.execute_fetchall(
            _KEYWORD_SEARCH_PG, (exact, like, like, like, limit)
        )
    else:
        rows = await db.execute_fetchall(
            _KEYWORD_SEARCH_SQLITE, (exact, like, like, like, exact, limit)
        )
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["cve_id"] = item["cve_id"]
        out.append(item)
    return out


def build_hybrid_results(
    *,
    keyword_rows: list[dict],
    vector_hits: list[dict],
    cards_by_id: dict[str, dict],
    limit: int,
    query_shape: QueryShape,
    mode: SearchMode,
) -> tuple[list[dict], str]:
    """Merge keyword + vector lists; return (results, method)."""
    kw_ids = [r["cve_id"] for r in keyword_rows if r.get("cve_id")]
    vec_ids = [h["cve_id"] for h in vector_hits if h.get("cve_id")]
    vec_sim = {
        h["cve_id"]: float(h.get("similarity") or 0.0)
        for h in vector_hits
        if h.get("cve_id")
    }

    if mode == "keyword" or (mode == "hybrid" and query_shape == "cve_id"):
        ordered_ids = kw_ids[:limit]
        method = "keyword" if mode == "keyword" else "keyword_first"
        ranked = [(cid, float(limit - i)) for i, cid in enumerate(ordered_ids)]
    elif mode == "semantic":
        if not vec_ids:
            ordered_ids = kw_ids[:limit]
            method = "keyword_fallback"
            ranked = [(cid, float(limit - i)) for i, cid in enumerate(ordered_ids)]
        else:
            ranked = [(cid, vec_sim.get(cid, 0.0)) for cid in vec_ids[:limit]]
            method = "semantic"
    else:
        # hybrid: RRF; short queries bias keyword by putting keyword list first
        # and duplicating weight via list order (RRF is commutative — use
        # weighted RRF instead).
        if not vec_ids:
            ranked = [(cid, float(limit - i)) for i, cid in enumerate(kw_ids[:limit])]
            method = "keyword_fallback"
        elif not kw_ids:
            ranked = [(cid, vec_sim.get(cid, 0.0)) for cid in vec_ids[:limit]]
            method = "semantic"
        else:
            kw_weight, vec_weight = _hybrid_weights(query_shape)
            scores: dict[str, float] = {}
            for rank, cid in enumerate(kw_ids, start=1):
                scores[cid] = scores.get(cid, 0.0) + kw_weight / (_RRF_K + rank)
            for rank, cid in enumerate(vec_ids, start=1):
                scores[cid] = scores.get(cid, 0.0) + vec_weight / (_RRF_K + rank)
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[
                :limit
            ]
            method = "hybrid"

    kw_set = set(kw_ids)
    vec_set = set(vec_ids)
    results: list[dict] = []
    for cid, score in ranked:
        card = cards_by_id.get(cid)
        if not card:
            continue
        reasons: list[str] = []
        if cid in kw_set:
            reasons.append("keyword")
        if cid in vec_set:
            reasons.append("vector")
        if not reasons:
            reasons.append("keyword" if method.startswith("keyword") else "vector")
        item: dict[str, Any] = {
            "entity_type": "cve",
            "entity_id": cid,
            "cve_id": cid,
            "score": round(float(score), 6),
            "match_reasons": reasons,
            "description": card.get("description") or "",
            "summary": card.get("summary") or "",
            "cvss_score": card.get("cvss_score"),
            "severity": card.get("severity"),
            "published": card.get("published"),
            "epss_score": card.get("epss_score"),
            "is_kev": bool(card.get("is_kev") or 0),
        }
        if cid in vec_sim:
            item["similarity"] = round(vec_sim[cid], 4)
        results.append(item)
    return results, method


def _hybrid_weights(shape: QueryShape) -> tuple[float, float]:
    if shape == "short":
        return 0.7, 0.3
    return 0.4, 0.6
