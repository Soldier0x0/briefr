"""Combined Incidents & News feed — RSS + ATLAS in parallel."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from database import get_atlas_case_studies, get_db
from feeds.incident_news import fetch_all_incident_news

logger = logging.getLogger(__name__)


def _atlas_study_to_card(study: dict) -> dict:
    techniques = [str(t).upper() for t in (study.get("techniques") or [])]
    study_id = study.get("study_id") or study.get("name") or ""
    summary = (study.get("summary") or study.get("name") or "").strip()
    return {
        "id": study_id,
        "source": "MITRE ATLAS",
        "sourceId": "atlas",
        "title": study.get("name") or "ATLAS case study",
        "description": summary[:280] + ("…" if len(summary) > 280 else ""),
        "publishedAt": study.get("date") or "",
        "url": f"https://atlas.mitre.org/studies/{study_id}",
        "techniques": techniques,
        "tags": [study["target"]] if study.get("target") else [],
        "actor": "",
        "target": study.get("target") or "",
        "kind": "atlas",
        "study_id": study_id,
        "cve_ids": study.get("cve_ids") or [],
        "technique_details": study.get("technique_details") or [],
    }


async def _load_news() -> tuple[list[dict], list[dict]]:
    db = await get_db()
    try:
        cards, errors = await fetch_all_incident_news(db)
        await db.commit()
        return cards, errors
    finally:
        await db.close()


async def _load_atlas(*, limit: int = 80) -> tuple[list[dict], list[dict]]:
    db = await get_db()
    try:
        studies = await get_atlas_case_studies(db, limit=limit)
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id, name FROM atlas_techniques"
        )
        tech_names = {r["technique_id"]: r["name"] for r in tech_rows}
    finally:
        await db.close()

    cards: list[dict] = []
    for row in studies:
        study = dict(row)
        technique_details = [
            {
                "technique_id": tid,
                "name": tech_names.get(tid, tid),
                "url": f"https://atlas.mitre.org/techniques/{tid}",
            }
            for tid in study.get("techniques", [])
        ]
        cards.append(_atlas_study_to_card({**study, "technique_details": technique_details}))
    return cards, []


async def fetch_combined_case_study_feed(
    *, atlas_limit: int = 80
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Load RSS news and ATLAS case studies concurrently (separate DB connections)."""
    news_result, atlas_result = await asyncio.gather(
        _load_news(),
        _load_atlas(limit=atlas_limit),
        return_exceptions=True,
    )

    cards: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if isinstance(news_result, BaseException):
        logger.warning("News feed load failed: %s", news_result)
        errors.append({"source": "News feeds", "message": str(news_result)})
    else:
        news_cards, news_errors = news_result
        cards.extend(news_cards)
        errors.extend(news_errors)

    if isinstance(atlas_result, BaseException):
        logger.warning("ATLAS feed load failed: %s", atlas_result)
        errors.append({"source": "MITRE ATLAS", "message": str(atlas_result)})
    else:
        atlas_cards, atlas_errors = atlas_result
        cards.extend(atlas_cards)
        errors.extend(atlas_errors)

    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)
    return cards, errors
