"""Hybrid / semantic CVE + technique search orchestration (E3/E6).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any

from db.embeddings_pgvector import (
    DEFAULT_EMBEDDING_DIMS,
    ENTITY_TYPE_CAMPAIGN,
    ENTITY_TYPE_CVE,
    ENTITY_TYPE_TECHNIQUE,
)
from db.embeddings_search import (
    SearchMode,
    ann_search_by_query_vector,
    build_hybrid_results,
    classify_query_shape,
    find_similar_via_embeddings_table,
    keyword_search_campaigns,
    keyword_search_cves,
    keyword_search_techniques,
)
from db.types import DbConnection
from ml.embeddings import (
    embed_query_text,
    embeddings_enabled,
    get_embeddings_model_name,
)

logger = logging.getLogger(__name__)

_MAX_LIMIT = 50
# Internal candidate budget when stack/severity/KEV post-filter (response still ≤ _MAX_LIMIT).
_MAX_FETCH_LIMIT = 150
_DEFAULT_LIMIT = 20


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def _hydrate_cve_cards(db: DbConnection, cve_ids: list[str]) -> dict[str, dict]:
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


async def _hydrate_technique_cards(
    db: DbConnection, technique_ids: list[str]
) -> dict[str, dict]:
    normalized = [t.upper() for t in technique_ids if t]
    if not normalized:
        return {}
    pg = _is_postgres_connection(db)
    out: dict[str, dict] = {}
    if pg:
        placeholders = ", ".join(f"${j}" for j in range(1, len(normalized) + 1))
    else:
        placeholders = ", ".join("?" for _ in normalized)
    rows = await db.execute_fetchall(
        f"""
        SELECT technique_id, name, description, tactic, url
        FROM mitre_techniques WHERE technique_id IN ({placeholders})
        """,
        tuple(normalized),
    )
    for row in rows:
        out[row["technique_id"]] = dict(row)
    return out


def _technique_results(
    keyword_rows: list[dict],
    vector_hits: list[dict],
    cards: dict[str, dict],
    limit: int,
) -> list[dict]:
    kw_ids = [r["technique_id"] for r in keyword_rows if r.get("technique_id")]
    vec_ids = [
        h["entity_id"]
        for h in vector_hits
        if h.get("entity_type") == ENTITY_TYPE_TECHNIQUE and h.get("entity_id")
    ]
    vec_sim = {
        h["entity_id"]: float(h.get("similarity") or 0.0)
        for h in vector_hits
        if h.get("entity_type") == ENTITY_TYPE_TECHNIQUE and h.get("entity_id")
    }
    ordered = list(dict.fromkeys(kw_ids + vec_ids))[:limit]
    out: list[dict] = []
    for tid in ordered:
        card = cards.get(tid)
        if not card:
            continue
        reasons: list[str] = []
        if tid in kw_ids:
            reasons.append("keyword")
        if tid in vec_ids:
            reasons.append("vector")
        item: dict[str, Any] = {
            "entity_type": ENTITY_TYPE_TECHNIQUE,
            "entity_id": tid,
            "technique_id": tid,
            "name": card.get("name") or tid,
            "description": card.get("description") or "",
            "tactic": card.get("tactic") or "",
            "url": card.get("url") or "",
            "score": round(vec_sim.get(tid, float(limit - len(out))), 6),
            "match_reasons": reasons or ["keyword"],
        }
        if tid in vec_sim:
            item["similarity"] = round(vec_sim[tid], 4)
        out.append(item)
    return out


async def _allowed_cve_ids_for_filters(
    db: DbConnection,
    candidate_ids: list[str],
    *,
    stack: str | None,
    severity: str | None,
    kev_only: bool,
) -> tuple[set[str] | None, list[str]]:
    """Return allowed CVE id set, or None when no CVE filters apply.

    Uses ``?`` placeholders (PostgresConnection adapts via ``pg_adapt``).
    Also returns normalized stack terms for ``meta``.
    """
    from routers.cves import _stack_match_clause

    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)
    sev = (severity or "").strip().upper() or None
    if not stack_clause and not sev and not kev_only:
        return None, stack_terms
    if not candidate_ids:
        return set(), stack_terms

    normalized = [c.upper() for c in candidate_ids if c]
    placeholders = ", ".join("?" for _ in normalized)
    conditions = [f"c.cve_id IN ({placeholders})"]
    params: list = list(normalized)

    if stack_clause:
        conditions.append(stack_clause)
        params.extend(stack_params)
    if sev:
        conditions.append("UPPER(c.severity) = ?")
        params.append(sev)
    if kev_only:
        # is_kev is INTEGER (Alembic 001 / SQLite) — same predicate as /api/cves.
        conditions.append("c.is_kev = 1")

    sql = f"SELECT c.cve_id FROM cves c WHERE {' AND '.join(conditions)}"
    rows = await db.execute_fetchall(sql, tuple(params))
    return {r["cve_id"] for r in rows}, stack_terms

async def _hydrate_campaign_cards(
    db: DbConnection, campaign_ids: list[str]
) -> dict[str, dict]:
    normalized = [c for c in campaign_ids if c]
    if not normalized:
        return {}
    pg = _is_postgres_connection(db)
    out: dict[str, dict] = {}
    if pg:
        placeholders = ", ".join(f"${j}" for j in range(1, len(normalized) + 1))
    else:
        placeholders = ", ".join("?" for _ in normalized)
    rows = await db.execute_fetchall(
        f"""
        SELECT campaign_id, label, adversary, malware_families, tags,
               lifecycle, member_count, confidence
        FROM correlation_campaigns
        WHERE campaign_id IN ({placeholders}) AND retracted_at IS NULL
        """,
        tuple(normalized),
    )
    for row in rows:
        out[row["campaign_id"]] = dict(row)
    return out


def _campaign_results(
    keyword_rows: list[dict],
    vector_hits: list[dict],
    cards: dict[str, dict],
    limit: int,
) -> list[dict]:
    kw_ids = [r["campaign_id"] for r in keyword_rows if r.get("campaign_id")]
    vec_ids = [
        h["entity_id"]
        for h in vector_hits
        if h.get("entity_type") == ENTITY_TYPE_CAMPAIGN and h.get("entity_id")
    ]
    vec_sim = {
        h["entity_id"]: float(h.get("similarity") or 0.0)
        for h in vector_hits
        if h.get("entity_type") == ENTITY_TYPE_CAMPAIGN and h.get("entity_id")
    }
    ordered = list(dict.fromkeys(kw_ids + vec_ids))[:limit]
    out: list[dict] = []
    for cid in ordered:
        card = cards.get(cid)
        if not card:
            continue
        reasons: list[str] = []
        if cid in kw_ids:
            reasons.append("keyword")
        if cid in vec_ids:
            reasons.append("vector")
        item: dict[str, Any] = {
            "entity_type": ENTITY_TYPE_CAMPAIGN,
            "entity_id": cid,
            "campaign_id": cid,
            "label": card.get("label") or cid,
            "adversary": card.get("adversary") or "",
            "lifecycle": card.get("lifecycle") or "",
            "member_count": int(card.get("member_count") or 0),
            "confidence": card.get("confidence") or "",
            "score": round(vec_sim.get(cid, float(limit - len(out))), 6),
            "match_reasons": reasons or ["keyword"],
        }
        if cid in vec_sim:
            item["similarity"] = round(vec_sim[cid], 4)
        out.append(item)
    return out


async def run_semantic_search(
    db,
    q: str,
    *,
    mode: SearchMode = "hybrid",
    limit: int = _DEFAULT_LIMIT,
    stack: str | None = None,
    severity: str | None = None,
    kev_only: bool = False,
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
                "stack_terms": [],
                "severity": None,
                "kev_only": False,
            },
        }

    capped = max(1, min(int(limit), _MAX_LIMIT))
    shape = classify_query_shape(text)
    mode_norm: SearchMode = (
        mode if mode in ("hybrid", "keyword", "semantic") else "hybrid"
    )

    # Over-fetch before filters so stack/severity don't empty a tiny keyword page.
    # Cap with _MAX_FETCH_LIMIT (not _MAX_LIMIT) so limit=50 still widens the candidate pool.
    fetch_limit = capped * 3 if (stack or severity or kev_only) else capped
    fetch_limit = max(1, min(fetch_limit, _MAX_FETCH_LIMIT))

    keyword_rows = await keyword_search_cves(db, text, limit=fetch_limit)
    tech_keyword = await keyword_search_techniques(db, text, limit=max(5, fetch_limit // 2))
    camp_keyword = await keyword_search_campaigns(db, text, limit=max(5, fetch_limit // 3))
    vector_hits: list[dict] = []

    need_vector = False
    if mode_norm == "semantic":
        need_vector = True
    elif mode_norm == "hybrid" and shape != "cve_id":
        need_vector = True

    if need_vector and embeddings_enabled():
        if shape == "cve_id":
            try:
                similar = await find_similar_via_embeddings_table(
                    db, text.upper(), get_embeddings_model_name(), limit=fetch_limit
                )
            except Exception:
                logger.exception("CVE-id semantic neighbor lookup failed")
                similar = None
            if similar:
                vector_hits = [
                    {
                        "entity_type": ENTITY_TYPE_CVE,
                        "entity_id": s["cve_id"],
                        "cve_id": s["cve_id"],
                        "similarity": s["similarity"],
                    }
                    for s in similar
                ]
        else:
            query_blob = await embed_query_text(text)
            if query_blob is not None:
                dims = len(query_blob) // 4
                try:
                    vector_hits = await ann_search_by_query_vector(
                        db,
                        get_embeddings_model_name(),
                        query_blob,
                        limit=fetch_limit,
                        expected_dim=dims or DEFAULT_EMBEDDING_DIMS,
                        entity_types=[
                            ENTITY_TYPE_CVE,
                            ENTITY_TYPE_TECHNIQUE,
                            ENTITY_TYPE_CAMPAIGN,
                        ],
                    )
                except Exception:
                    logger.exception("vector ANN search failed — keyword only")
                    vector_hits = []

    cve_vector_hits = [
        {
            "cve_id": h.get("cve_id") or h.get("entity_id"),
            "similarity": h.get("similarity"),
        }
        for h in vector_hits
        if (h.get("entity_type") or ENTITY_TYPE_CVE) == ENTITY_TYPE_CVE
    ]

    ids = list(
        dict.fromkeys(
            [r["cve_id"] for r in keyword_rows]
            + [h["cve_id"] for h in cve_vector_hits if h.get("cve_id")]
        )
    )
    allowed_ids, stack_terms = await _allowed_cve_ids_for_filters(
        db,
        ids,
        stack=stack,
        severity=severity,
        kev_only=bool(kev_only),
    )
    if allowed_ids is not None:
        keyword_rows = [r for r in keyword_rows if r.get("cve_id") in allowed_ids]
        cve_vector_hits = [h for h in cve_vector_hits if h.get("cve_id") in allowed_ids]
        ids = [i for i in ids if i in allowed_ids]

    cards = await _hydrate_cve_cards(db, ids)
    for row in keyword_rows:
        cards[row["cve_id"]] = row

    tech_ids = list(
        dict.fromkeys(
            [r["technique_id"] for r in tech_keyword]
            + [
                h["entity_id"]
                for h in vector_hits
                if h.get("entity_type") == ENTITY_TYPE_TECHNIQUE
            ]
        )
    )
    # Stack/severity/KEV are CVE filters — techniques/campaigns stay unfiltered.
    tech_cards = await _hydrate_technique_cards(db, tech_ids)
    for row in tech_keyword:
        tech_cards[row["technique_id"]] = row

    camp_ids = list(
        dict.fromkeys(
            [r["campaign_id"] for r in camp_keyword]
            + [
                h["entity_id"]
                for h in vector_hits
                if h.get("entity_type") == ENTITY_TYPE_CAMPAIGN
            ]
        )
    )
    camp_cards = await _hydrate_campaign_cards(db, camp_ids)
    for row in camp_keyword:
        camp_cards[row["campaign_id"]] = row

    # When CVE filters are active, shrink typed-hit budgets so filters keep CVE slots.
    if allowed_ids is not None:
        tech_budget = (
            min(max(2, capped // 5), capped - 1) if capped > 1 and tech_ids else 0
        )
        camp_budget = (
            min(max(1, capped // 8), capped - 1) if capped > 1 and camp_ids else 0
        )
    else:
        tech_budget = (
            min(max(3, capped // 4), capped - 1) if capped > 1 and tech_ids else 0
        )
        camp_budget = (
            min(max(2, capped // 6), capped - 1) if capped > 1 and camp_ids else 0
        )
    # Keep at least one CVE slot when typed hits compete for the page.
    reserved = min(tech_budget + camp_budget, max(0, capped - 1))
    if reserved and tech_budget + camp_budget > reserved:
        # Prefer techniques slightly when both present.
        camp_budget = min(camp_budget, max(0, reserved - min(tech_budget, reserved)))
        tech_budget = min(tech_budget, reserved - camp_budget)
    cve_budget = max(1, capped - tech_budget - camp_budget)

    cve_results, method = build_hybrid_results(
        keyword_rows=keyword_rows,
        vector_hits=cve_vector_hits,
        cards_by_id=cards,
        limit=cve_budget,
        query_shape=shape,
        mode=mode_norm,
    )

    tech_results = _technique_results(
        tech_keyword, vector_hits, tech_cards, limit=tech_budget
    )
    camp_results = _campaign_results(
        camp_keyword, vector_hits, camp_cards, limit=camp_budget
    )

    # Reserve slots so typed hits are not sliced away when CVE fill is full.
    combined = list(cve_results)
    seen = {r["entity_id"] for r in combined}
    for hit in tech_results + camp_results:
        if hit["entity_id"] in seen:
            continue
        if len(combined) >= capped:
            break
        combined.append(hit)
        seen.add(hit["entity_id"])

    return {
        "data": combined[:capped],
        "meta": {
            "method": method,
            "mode_requested": mode_norm,
            "query_shape": shape,
            "q": text[:200],
            "embeddings_enabled": embeddings_enabled(),
            "includes_techniques": bool(tech_results),
            "includes_campaigns": bool(camp_results),
            "stack_terms": stack_terms,
            "severity": (severity or "").strip().upper() or None,
            "kev_only": bool(kev_only),
        },
    }
