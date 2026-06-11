"""Combined Incidents & News feed — RSS + ATLAS served from a precomputed snapshot."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from database import get_atlas_case_studies, get_db, get_feed_cache, set_feed_cache
from feeds.incident_news import fetch_all_incident_news_parallel

logger = logging.getLogger(__name__)

SNAPSHOT_CACHE_KEY = "incident_feed:snapshot"
SNAPSHOT_ATLAS_LIMIT = 100
# Snapshots are always served if present; staleness is reported via meta.
SNAPSHOT_MAX_AGE_HOURS = 24 * 7


def get_incident_feed_refresh_minutes() -> int:
    try:
        return max(5, int(os.environ.get("INCIDENT_FEED_REFRESH_MINUTES", "30")))
    except ValueError:
        return 30


def _is_snapshot_stale(generated_at: str) -> bool:
    """Stale when older than two refresh intervals (one missed cycle)."""
    if not generated_at:
        return True
    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    threshold = timedelta(minutes=get_incident_feed_refresh_minutes() * 2)
    return datetime.now(timezone.utc) - generated > threshold


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


_build_lock = asyncio.Lock()
_background_tasks: set[asyncio.Task[None]] = set()


async def build_incident_feed_snapshot() -> dict[str, Any]:
    """Build and persist the combined RSS + ATLAS snapshot.

    Runs in the scheduler job (and in the background on a cold cache miss).
    RSS sources are fetched in parallel; everything uses one SQLite
    connection. Serialized so overlapping triggers cannot race.
    """
    async with _build_lock:
        return await _build_snapshot()


async def _build_snapshot() -> dict[str, Any]:
    db = await get_db()
    news_cards: list[dict[str, Any]] = []
    atlas_cards: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        try:
            news_cards, news_errors = await fetch_all_incident_news_parallel(db)
            errors.extend(news_errors)
        except Exception as exc:
            logger.warning("News feed load failed: %s", exc)
            errors.append({"source": "News feeds", "message": str(exc)})

        try:
            atlas_cards, atlas_errors = await _load_atlas_cards(
                db, limit=SNAPSHOT_ATLAS_LIMIT
            )
            errors.extend(atlas_errors)
        except Exception as exc:
            logger.warning("ATLAS feed load failed: %s", exc)
            errors.append({"source": "MITRE ATLAS", "message": str(exc)})

        snapshot = {
            "news": news_cards,
            "atlas": atlas_cards,
            "errors": errors,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await set_feed_cache(db, SNAPSHOT_CACHE_KEY, snapshot)
            await db.commit()
        except Exception as exc:
            # Persist failure (e.g. write contention during bootstrap ingest)
            # must not lose the in-memory result; next cycle will persist.
            logger.warning("Incident feed snapshot persist failed: %s", exc)
    finally:
        await db.close()

    logger.info(
        "Incident feed snapshot built: %d news, %d ATLAS, %d errors",
        len(news_cards),
        len(atlas_cards),
        len(errors),
    )
    return snapshot


async def _read_snapshot() -> dict[str, Any] | None:
    db = await get_db()
    try:
        return await get_feed_cache(
            db, SNAPSHOT_CACHE_KEY, max_age_hours=SNAPSHOT_MAX_AGE_HOURS
        )
    finally:
        await db.close()


def _schedule_background_build() -> None:
    if _build_lock.locked():
        return

    async def _runner() -> None:
        try:
            await build_incident_feed_snapshot()
        except Exception as exc:
            logger.error("Background incident snapshot build failed: %s", exc)

    task = asyncio.create_task(_runner())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def get_incident_feed(
    *, atlas_limit: int = 80
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    """Serve the Incidents & News feed from the snapshot — pure read.

    A cold cache miss (first boot before the scheduler warm-up) never blocks
    the request: it kicks off a background build and reports `warming` so
    clients skip caching the empty result.
    """
    snapshot = await _read_snapshot()
    if snapshot is None:
        _schedule_background_build()
        meta = {
            "refreshed_at": None,
            "stale": True,
            "warming": True,
            "refresh_interval_minutes": get_incident_feed_refresh_minutes(),
        }
        return [], [], meta

    cards = list(snapshot.get("news") or [])
    cards.extend((snapshot.get("atlas") or [])[:atlas_limit])
    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)

    generated_at = snapshot.get("generated_at") or ""
    meta = {
        "refreshed_at": generated_at or None,
        "stale": _is_snapshot_stale(generated_at),
        "warming": False,
        "refresh_interval_minutes": get_incident_feed_refresh_minutes(),
    }
    return cards, list(snapshot.get("errors") or []), meta


async def get_incident_feed_status() -> dict[str, Any]:
    """Snapshot freshness for /api/health — never triggers a build."""
    snapshot = await _read_snapshot()
    if snapshot is None:
        return {"last_refresh": None, "stale": True}
    generated_at = snapshot.get("generated_at") or ""
    return {
        "last_refresh": generated_at or None,
        "stale": _is_snapshot_stale(generated_at),
    }
