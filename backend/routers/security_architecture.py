"""Security Architecture read API (Threat Modeling module TM-1+).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from security_architecture.corpus_loader import get_corpus
from security_architecture.posture import build_overview
from threat_model.scenarios import build_threat_scenarios

router = APIRouter()


@router.get("/api/security-architecture/manifest")
async def security_architecture_manifest():
    """Corpus version and section index."""
    corpus = get_corpus()
    return {
        "manifest": corpus.manifest,
        "counts": {
            "components": len(corpus.components),
            "controls": len(corpus.controls),
            "trust_boundaries": len(corpus.trust_boundaries),
            "abuse_cases": len(corpus.abuse_cases),
            "threat_scenarios": len(corpus.threat_scenarios),
            "risks": len(corpus.risks),
            "decisions": len(corpus.security_decisions),
            "reviews": len(corpus.reviews),
        },
    }


@router.get("/api/security-architecture/overview")
async def security_architecture_overview():
    """Landing posture summary cards and architecture stack."""
    return build_overview(get_corpus())


@router.get("/api/security-architecture/graph/architecture")
async def security_architecture_graph():
    """Full system architecture graph."""
    corpus = get_corpus()
    return {
        "graph": corpus.architecture_graph,
        "components": corpus.components,
    }


@router.get("/api/security-architecture/graph/attack-surface")
async def security_architecture_attack_surface():
    """Attack surface score and exposure nodes."""
    return get_corpus().attack_surface_graph


@router.get("/api/security-architecture/trust-boundaries")
async def security_architecture_trust_boundaries():
    return {"trust_boundaries": get_corpus().trust_boundaries}


@router.get("/api/security-architecture/stride")
async def security_architecture_stride():
    return {"matrices": get_corpus().stride}


@router.get("/api/security-architecture/owasp")
async def security_architecture_owasp():
    corpus = get_corpus()
    return {
        "owasp_top10": corpus.owasp_top10,
        "owasp_api": corpus.owasp_api,
    }


@router.get("/api/security-architecture/controls")
async def security_architecture_controls():
    return {"controls": get_corpus().controls}


@router.get("/api/security-architecture/abuse-cases")
async def security_architecture_abuse_cases():
    return {"abuse_cases": get_corpus().abuse_cases}


@router.get("/api/security-architecture/threat-scenarios")
async def security_architecture_threat_scenarios(
    stack: str | None = Query(default=None, max_length=500),
):
    """Operational path scenarios from corpus plus live ATT&CK scenarios."""
    corpus = get_corpus()
    db = await get_db()
    try:
        live = await build_threat_scenarios(db, stack)
    finally:
        await db.close()
    return {
        "operational_scenarios": corpus.threat_scenarios,
        "attack_scenarios": live.get("scenarios", []),
        "meta": live.get("meta", {}),
    }


@router.get("/api/security-architecture/risks")
async def security_architecture_risks():
    return {"risks": get_corpus().risks}


@router.get("/api/security-architecture/decisions")
async def security_architecture_decisions():
    return {"decisions": get_corpus().security_decisions}


@router.get("/api/security-architecture/reviews")
async def security_architecture_reviews():
    return {"reviews": get_corpus().reviews}


@router.get("/api/security-architecture/capec")
async def security_architecture_capec():
    return {"patterns": get_corpus().capec_mappings}


@router.get("/api/security-architecture/frameworks/nist-csf")
async def security_architecture_nist():
    return {"functions": get_corpus().nist_csf}


@router.get("/api/security-architecture/frameworks/asvs")
async def security_architecture_asvs():
    return {"chapters": get_corpus().asvs}


@router.get("/api/security-architecture/search")
async def security_architecture_search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Search corpus entities by id, title, or summary."""
    needle = q.lower()
    corpus = get_corpus()
    hits: list[dict] = []
    for entity_id, row in corpus.entity_index().items():
        hay = " ".join(
            str(row.get(k, "")) for k in ("id", "title", "summary", "description")
        ).lower()
        if needle in hay or needle in entity_id.lower():
            hits.append(
                {
                    "id": entity_id,
                    "entity_type": row.get("_entity_type"),
                    "title": row.get("title"),
                    "summary": row.get("summary"),
                }
            )
        if len(hits) >= limit:
            break
    return {"query": q, "results": hits[:limit]}


@router.get("/api/security-architecture/context/{entity_type}/{entity_id}")
async def security_architecture_context(entity_type: str, entity_id: str):
    """Context rail payload for a selected corpus entity."""
    corpus = get_corpus()
    row = corpus.entity_index().get(entity_id)
    if not row:
        raise HTTPException(status_code=404, detail="Entity not found")
    normalized_type = entity_type.replace("-", "_").rstrip("s")
    actual_type = str(row.get("_entity_type", ""))
    if normalized_type and normalized_type not in actual_type and actual_type not in normalized_type:
        raise HTTPException(status_code=404, detail="Entity not found")
    related: list[dict] = []
    link_ids = list(row.get("related_ids") or [])
    for key in ("security_controls", "controls", "threats", "mitigations"):
        val = row.get(key)
        if isinstance(val, list):
            link_ids.extend(str(v) for v in val)
    for rid in link_ids:
        ref = corpus.entity_index().get(rid)
        if ref:
            related.append(
                {
                    "id": rid,
                    "title": ref.get("title"),
                    "entity_type": ref.get("_entity_type"),
                }
            )
    return {
        "entity": {k: v for k, v in row.items() if not k.startswith("_")},
        "entity_type": actual_type,
        "related": related,
        "documentation": row.get("source_refs") or [],
    }
