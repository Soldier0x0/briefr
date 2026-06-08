"""Combined Incidents & News feed — RSS + ATLAS on one DB connection."""

from __future__ import annotations

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


async def _load_atlas_cards(
    db, *, limit: int
) -> tuple[list[dict], list[dict]]:
    studies = await get_atlas_case_studies(db, limit=limit)
    tech_rows = await db.execute_fetchall(
        "SELECT technique_id, name FROM atlas_techniques"
    )
    tech_names = {r["technique_id"]: r["name"] for r in tech_rows}

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
    """Load RSS news then ATLAS case studies on a single SQLite connection."""
    db = await get_db()
    cards: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        try:
            news_cards, news_errors = await fetch_all_incident_news(db)
            cards.extend(news_cards)
            errors.extend(news_errors)
        except Exception as exc:
            logger.warning("News feed load failed: %s", exc)
            errors.append({"source": "News feeds", "message": str(exc)})

        try:
            atlas_cards, atlas_errors = await _load_atlas_cards(db, limit=atlas_limit)
            cards.extend(atlas_cards)
            errors.extend(atlas_errors)
        except Exception as exc:
            logger.warning("ATLAS feed load failed: %s", exc)
            errors.append({"source": "MITRE ATLAS", "message": str(exc)})

        await db.commit()
    finally:
        await db.close()

    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)
    return cards, errors
