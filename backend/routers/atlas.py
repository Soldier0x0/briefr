"""MITRE ATLAS + Case Studies endpoints, moved verbatim from main.py
(V1.2 §5.2 router split, phase 2). No behavior change; the one inline
import (`fetch_all_incident_news`) was hoisted to module top per house
convention.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from fastapi import APIRouter, Query

from database import (
    get_atlas_case_studies,
    get_atlas_techniques_grouped,
    get_db,
)
from feeds.case_study_feed import get_incident_feed
from feeds.incident_news import fetch_all_incident_news

router = APIRouter()


@router.get("/api/atlas/techniques")
async def atlas_techniques_grouped():
    """MITRE ATLAS techniques grouped by tactic (AI/ML threats — not Enterprise ATT&CK)."""
    db = await get_db()
    try:
        groups = await get_atlas_techniques_grouped(db)
    finally:
        await db.close()
    return {"data": groups, "source": "MITRE ATLAS"}


@router.get("/api/case-studies/news")
async def case_studies_news():
    """Cybersecurity news RSS feeds for the Case Studies tab (server-side fetch)."""
    db = await get_db()
    try:
        cards, errors = await fetch_all_incident_news(db)
        await db.commit()
    finally:
        await db.close()
    return {"data": cards, "errors": errors}


@router.get("/api/case-studies/feed")
async def case_studies_feed(
    atlas_limit: int = Query(default=80, ge=1, le=100),
):
    """Combined RSS news + ATLAS case studies, served from the precomputed snapshot."""
    cards, errors, meta = await get_incident_feed(atlas_limit=atlas_limit)
    return {"data": cards, "errors": errors, "meta": meta}


@router.get("/api/atlas/casestudies")
async def atlas_case_studies(
    limit: int = Query(default=50, ge=1, le=100),
):
    """Recent ATLAS case studies with technique and CVE references."""
    db = await get_db()
    try:
        studies = await get_atlas_case_studies(db, limit=limit)
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id, name FROM atlas_techniques"
        )
        tech_names = {r["technique_id"]: r["name"] for r in tech_rows}
    finally:
        await db.close()

    for study in studies:
        study["technique_details"] = [
            {
                "technique_id": tid,
                "name": tech_names.get(tid, tid),
                "url": f"https://atlas.mitre.org/techniques/{tid}",
            }
            for tid in study.get("techniques", [])
        ]

    return {"data": studies, "source": "MITRE ATLAS"}
