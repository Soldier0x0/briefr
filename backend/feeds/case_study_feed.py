"""Combined Incidents & News feed — RSS + ATLAS served from a precomputed snapshot."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from database import get_atlas_case_studies, get_db, get_feed_cache, set_feed_cache
from feeds.incident_news import (
    extract_cve_ids,
    fetch_all_incident_news_parallel,
    fetch_rss_source,
    get_rss_sources_status,
)
from feeds.incident_sources import INCIDENT_RSS_SOURCES

logger = logging.getLogger(__name__)

SNAPSHOT_CACHE_KEY = "incident_feed:snapshot"
SNAPSHOT_ATLAS_LIMIT = 100
# Snapshots are always served if present; staleness is reported via meta.
SNAPSHOT_MAX_AGE_HOURS = 24 * 7

INCIDENT_RSS_SOURCE_IDS = {source["id"] for source in INCIDENT_RSS_SOURCES}
INCIDENT_SOURCE_IDS = INCIDENT_RSS_SOURCE_IDS | {"atlas"}
_ACTIVE_ERROR_SOURCES = {s["label"] for s in INCIDENT_RSS_SOURCES} | {
    "MITRE ATLAS",
    "News feeds",
}


def _ensure_news_cve_ids(card: dict[str, Any]) -> dict[str, Any]:
    """Backfill cve_ids on stale snapshot rows that predate RSS↔CVE linking."""
    if not isinstance(card, dict):
        return card
    if card.get("kind") == "atlas":
        return card
    existing = card.get("cve_ids")
    if isinstance(existing, list):
        return card
    ids = extract_cve_ids(card.get("title") or "", card.get("description") or "")
    return {**card, "cve_ids": ids}


def _prune_news_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop RSS cards from removed sources (stale snapshot rows)."""
    return [
        _ensure_news_cve_ids(c)
        for c in cards
        if c.get("sourceId") in INCIDENT_RSS_SOURCE_IDS
    ]


def _card_mentions_cve(card: dict[str, Any], cve_key: str) -> bool:
    key = (cve_key or "").strip().upper()
    if not key:
        return False
    ids = card.get("cve_ids")
    if isinstance(ids, list) and key in {str(x).upper() for x in ids}:
        return True
    # Atlas / legacy rows may only mention the CVE in free text.
    hay = f"{card.get('title') or ''} {card.get('description') or ''}"
    return key in hay.upper()


async def get_related_news_for_cve(
    cve_id: str, *, limit: int = 8
) -> list[dict[str, Any]]:
    """News/ATLAS cards from the incident snapshot that mention this CVE."""
    cve_key = (cve_id or "").strip().upper()
    if not cve_key.startswith("CVE-"):
        return []
    snapshot = await _read_snapshot()
    if not snapshot:
        return []
    cards = _prune_news_cards(list(snapshot.get("news") or []))
    cards.extend(list(snapshot.get("atlas") or []))
    hits = [c for c in cards if _card_mentions_cve(c, cve_key)]
    hits.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)
    out: list[dict[str, Any]] = []
    for card in hits[: max(1, min(limit, 20))]:
        out.append(
            {
                "title": card.get("title") or "",
                "source": card.get("source") or "",
                "url": card.get("url") or "",
                "publishedAt": card.get("publishedAt") or "",
                "kind": card.get("kind") or "news",
            }
        )
    return out


def _prune_errors(errors: list[Any]) -> list[Any]:
    return [
        e
        for e in errors
        if isinstance(e, dict) and e.get("source") in _ACTIVE_ERROR_SOURCES
    ]


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
            "news": _prune_news_cards(news_cards),
            "atlas": atlas_cards,
            "errors": _prune_errors(errors),
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
    # Registered for strong-ref + bounded shutdown drain (PR-R1).
    from task_registry import register_background_task

    register_background_task(task)


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

    cards = _prune_news_cards(list(snapshot.get("news") or []))
    cards.extend((snapshot.get("atlas") or [])[:atlas_limit])
    cards.sort(key=lambda c: c.get("publishedAt") or "", reverse=True)

    generated_at = snapshot.get("generated_at") or ""
    meta = {
        "refreshed_at": generated_at or None,
        "stale": _is_snapshot_stale(generated_at),
        "warming": False,
        "refresh_interval_minutes": get_incident_feed_refresh_minutes(),
    }
    return cards, _prune_errors(list(snapshot.get("errors") or [])), meta


async def refresh_incident_feed_sources(
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Refresh selected incident-feed sources and merge into the snapshot.

    * RSS source ids — force re-fetch that feed (bypass 30-minute cache).
    * ``atlas`` — reload case studies from the local DB (run
      ``weekly_mitre_refresh`` first to pull upstream MITRE data).
    * ``None`` or empty — full rebuild (all RSS + ATLAS).
    """
    if not source_ids:
        return await build_incident_feed_snapshot()

    unknown = set(source_ids) - INCIDENT_SOURCE_IDS
    if unknown:
        raise ValueError(
            f"Unknown incident source(s): {sorted(unknown)}. "
            f"Valid: {sorted(INCIDENT_SOURCE_IDS)}"
        )

    requested = set(source_ids)
    async with _build_lock:
        db = await get_db()
        news_cards: list[dict[str, Any]] = []
        atlas_cards: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        try:
            existing = await get_feed_cache(
                db, SNAPSHOT_CACHE_KEY, max_age_hours=SNAPSHOT_MAX_AGE_HOURS
            )
            news_cards = list((existing or {}).get("news") or [])
            atlas_cards = list((existing or {}).get("atlas") or [])
            errors = list((existing or {}).get("errors") or [])

            rss_requested = requested & INCIDENT_RSS_SOURCE_IDS
            if rss_requested:
                news_cards = [
                    card
                    for card in news_cards
                    if card.get("sourceId") not in rss_requested
                ]
                errors = [
                    err
                    for err in errors
                    if isinstance(err, dict)
                    and err.get("source")
                    not in {
                        s["label"]
                        for s in INCIDENT_RSS_SOURCES
                        if s["id"] in rss_requested
                    }
                ]
                for source in INCIDENT_RSS_SOURCES:
                    if source["id"] not in rss_requested:
                        continue
                    try:
                        items = await fetch_rss_source(db, source, force=True)
                        news_cards.extend(items)
                    except Exception as exc:
                        logger.warning(
                            "RSS refresh failed for %s: %s", source["label"], exc
                        )
                        errors.append(
                            {
                                "source": source["label"],
                                "message": str(exc) or "Failed to load feed",
                            }
                        )
                news_cards.sort(
                    key=lambda c: c.get("publishedAt") or "", reverse=True
                )

            if "atlas" in requested:
                errors = [
                    err
                    for err in errors
                    if isinstance(err, dict) and err.get("source") != "MITRE ATLAS"
                ]
                try:
                    atlas_cards, atlas_errors = await _load_atlas_cards(
                        db, limit=SNAPSHOT_ATLAS_LIMIT
                    )
                    errors.extend(atlas_errors)
                except Exception as exc:
                    logger.warning("ATLAS feed reload failed: %s", exc)
                    errors.append(
                        {"source": "MITRE ATLAS", "message": str(exc)}
                    )

            snapshot = {
                "news": _prune_news_cards(news_cards),
                "atlas": atlas_cards,
                "errors": _prune_errors(errors),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            await set_feed_cache(db, SNAPSHOT_CACHE_KEY, snapshot)
            await db.commit()
        finally:
            await db.close()

        logger.info(
            "Incident feed partial refresh (%s): %d news, %d ATLAS, %d errors",
            ",".join(sorted(requested)),
            len(news_cards),
            len(atlas_cards),
            len(errors),
        )
        return snapshot


async def get_incident_feed_status() -> dict[str, Any]:
    """Snapshot freshness for /api/health — never triggers a build."""
    snapshot = await _read_snapshot()
    generated_at = (snapshot or {}).get("generated_at") or ""
    stale = True if snapshot is None else _is_snapshot_stale(generated_at)

    db = await get_db()
    try:
        rss_sources = await get_rss_sources_status(db)
        count_row = await db.execute_fetchall(
            "SELECT COUNT(*) AS cnt FROM atlas_case_studies"
        )
        atlas_count = int(count_row[0]["cnt"]) if count_row else 0
        latest_atlas = await db.execute_fetchall(
            """
            SELECT date FROM atlas_case_studies
            WHERE date IS NOT NULL AND date != ''
            ORDER BY date DESC
            LIMIT 1
            """
        )
        atlas_latest_date = latest_atlas[0]["date"] if latest_atlas else None
    finally:
        await db.close()

    snapshot_news = (snapshot or {}).get("news") or []
    snapshot_atlas = (snapshot or {}).get("atlas") or []
    snapshot_errors = (snapshot or {}).get("errors") or []
    errors_by_label = {
        e.get("source"): e.get("message", "")
        for e in snapshot_errors
        if isinstance(e, dict) and e.get("source")
    }

    sources: list[dict[str, Any]] = []
    for src in rss_sources:
        in_snapshot = sum(
            1 for card in snapshot_news if card.get("sourceId") == src["id"]
        )
        sources.append(
            {
                **src,
                "snapshot_item_count": in_snapshot,
                "last_error": errors_by_label.get(src["label"], ""),
            }
        )

    sources.append(
        {
            "id": "atlas",
            "label": "MITRE ATLAS",
            "kind": "atlas",
            "item_count": atlas_count,
            "snapshot_item_count": len(snapshot_atlas),
            "cached_at": atlas_latest_date,
            "stale": atlas_count == 0,
            "last_error": errors_by_label.get("MITRE ATLAS", ""),
            "upstream_job_id": "weekly_mitre_refresh",
        }
    )

    return {
        "last_refresh": generated_at or None,
        "stale": stale,
        "sources": sources,
    }
