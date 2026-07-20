"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

import asyncio
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from correlation.engine import get_correlation_for_cve
from db.cache import get_cve_exploits_latest_fetched_at, get_feed_cache_timestamp
from database import (
    get_atlas_case_studies_for_cve,
    get_atlas_techniques_for_cve,
    get_cve_summaries_by_ids,
    get_db,
    get_epss_history,
    get_feed_cache,
    get_related_cves,
    get_techniques_for_cve,
    get_watchlist_entry,
)
from feeds.case_study_feed import get_related_news_for_cve
from feeds.extended import enrich_cve_circl, load_public_exploits_for_cve
from feeds.osv import fetch_osv_by_cve
from feeds.otx import load_otx_pulses_for_cve
from intel.provenance import (
    derive_correlation_provenance,
    derive_exploit_provenance,
    otx_configured_from_env,
)
from ml.embeddings import embeddings_enabled, find_similar_cves
from routers._validators import require_cve_id
from scoring.risk import calculate_momentum
from templates.intelligence import (
    epss_sentence_or_fallback,
    exploit_sentence,
    exploits_from_cve,
    kev_sentence,
    patch_sentence,
    severity_sentence,
)

from .common import row_to_cve_dict

logger = logging.getLogger(__name__)
detail_router = APIRouter()


@detail_router.get("/api/cves/{cve_id}/sentences")
async def get_cve_sentences(cve_id: str):
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, cvss_score, severity, is_kev, epss_score,
                   has_poc, patch_available, source_urls
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        row = dict(rows[0])
        is_kev = bool(row.get("is_kev", 0))
        has_poc = bool(row.get("has_poc", 0))
        patch_available = bool(row.get("patch_available", 0))

        source_urls = row.get("source_urls") or "[]"
        if isinstance(source_urls, str):
            try:
                source_urls = json.loads(source_urls)
            except (json.JSONDecodeError, TypeError):
                source_urls = []

        kev_rows = await db.execute_fetchall(
            """
            SELECT due_date, required_action
            FROM kev_deadlines
            WHERE cve_id = ?
            """,
            (cve_key,),
        )

        sploitus_exploits = await load_public_exploits_for_cve(
            db,
            cve_key,
            has_poc=bool(row.get("has_poc")),
            source_urls=source_urls,
        )
        await db.commit()
    finally:
        await db.close()

    due_date = ""
    fix = ""
    if kev_rows:
        kev_row = dict(kev_rows[0])
        due_date = (kev_row.get("due_date") or "").strip()
        fix = (kev_row.get("required_action") or "").strip()

    exploit_items = [{"type": e.get("type", "poc")} for e in sploitus_exploits]
    if not exploit_items:
        exploit_items = exploits_from_cve(has_poc, source_urls)
    cvss = row.get("cvss_score")

    return {
        "cve_id": cve_key,
        "risk": severity_sentence(row.get("severity"), cvss),
        "exploit_likelihood": epss_sentence_or_fallback(row.get("epss_score"), is_kev),
        "public_exploits": exploit_sentence(exploit_items),
        "patch": patch_sentence(patch_available, fix),
        "kev": kev_sentence(is_kev, due_date),
        "kev_required_action": fix or None,
    }


@detail_router.get("/api/cves/{cve_id}/epss-history")
async def get_cve_epss_history(cve_id: str):
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
    db = await get_db()
    try:
        exists = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,)
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
        history = await get_epss_history(db, cve_key, days=30)
    finally:
        await db.close()

    return history


@detail_router.get("/api/cves/{cve_id}/related")
async def get_cve_related(
    cve_id: str,
    limit: int = Query(default=5, ge=1, le=20),
):
    """Related CVEs — semantic (embeddings) when enabled and vectors exist,
    otherwise the deterministic shared-product heuristic. Additive response:
    `data` keeps its shape; embedding results add a `similarity` field and
    `meta.method` reports which path produced them."""
    cve_id = require_cve_id(cve_id)

    cve_key = cve_id
    db = await get_db()
    try:
        exists = await db.execute_fetchall(
            "SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,)
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        related: list[dict] = []
        method = "product_heuristic"
        if embeddings_enabled():
            try:
                # Pure BLOB scan over scheduler-computed vectors — no model
                # inference in the request path (ROADMAP ML placement rules).
                similar = await find_similar_cves(db, cve_key, limit=limit)
            except Exception as exc:
                logger.error("Embedding similarity failed for %s: %s", cve_key, exc)
                similar = None
            if similar:
                summaries = await get_cve_summaries_by_ids(
                    db, [s["cve_id"] for s in similar]
                )
                for s in similar:
                    base = summaries.get(s["cve_id"])
                    if base:
                        related.append({**base, "similarity": s["similarity"]})
                if related:
                    method = "embeddings"

        if not related:
            related = await get_related_cves(db, cve_key, limit=limit)
            method = "product_heuristic"
    finally:
        await db.close()

    return {"data": related, "meta": {"method": method}}


async def _drawer_sentences_payload(db, cve_key: str) -> dict:
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, cvss_score, severity, is_kev, epss_score,
               has_poc, patch_available, source_urls
        FROM cves
        WHERE cve_id = ?
        """,
        (cve_key,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

    row = dict(rows[0])
    is_kev = bool(row.get("is_kev", 0))
    has_poc = bool(row.get("has_poc", 0))
    patch_available = bool(row.get("patch_available", 0))

    source_urls = row.get("source_urls") or "[]"
    if isinstance(source_urls, str):
        try:
            source_urls = json.loads(source_urls)
        except (json.JSONDecodeError, TypeError):
            source_urls = []

    kev_rows = await db.execute_fetchall(
        """
        SELECT due_date, required_action
        FROM kev_deadlines
        WHERE cve_id = ?
        """,
        (cve_key,),
    )

    sploitus_exploits = await load_public_exploits_for_cve(
        db,
        cve_key,
        has_poc=bool(row.get("has_poc")),
        source_urls=source_urls,
    )

    due_date = ""
    fix = ""
    if kev_rows:
        kev_row = dict(kev_rows[0])
        due_date = (kev_row.get("due_date") or "").strip()
        fix = (kev_row.get("required_action") or "").strip()

    exploit_items = [{"type": e.get("type", "poc")} for e in sploitus_exploits]
    if not exploit_items:
        exploit_items = exploits_from_cve(has_poc, source_urls)
    cvss = row.get("cvss_score")

    return {
        "cve_id": cve_key,
        "risk": severity_sentence(row.get("severity"), cvss),
        "exploit_likelihood": epss_sentence_or_fallback(row.get("epss_score"), is_kev),
        "public_exploits": exploit_sentence(exploit_items),
        "patch": patch_sentence(patch_available, fix),
        "kev": kev_sentence(is_kev, due_date),
        "kev_required_action": fix or None,
    }


async def _drawer_related_payload(db, cve_key: str, *, limit: int = 5) -> dict:
    related: list[dict] = []
    method = "product_heuristic"
    if embeddings_enabled():
        try:
            similar = await find_similar_cves(db, cve_key, limit=limit)
        except Exception as exc:
            logger.error("Embedding similarity failed for %s: %s", cve_key, exc)
            similar = None
        if similar:
            summaries = await get_cve_summaries_by_ids(db, [s["cve_id"] for s in similar])
            for s in similar:
                base = summaries.get(s["cve_id"])
                if base:
                    related.append({**base, "similarity": s["similarity"]})
            if related:
                method = "embeddings"

    if not related:
        related = await get_related_cves(db, cve_key, limit=limit)
        method = "product_heuristic"

    return {"data": related, "meta": {"method": method}}


async def _drawer_db_task(coro_fn):
    """Run one drawer sub-fetch on its own pool connection (asyncpg is single-flight per conn)."""
    task_db = await get_db()
    try:
        result = await coro_fn(task_db)
        await task_db.commit()
        return result
    finally:
        await task_db.close()


async def _build_cve_drawer_bundle(db, cve_key: str, *, sector: str = "") -> dict:
    exists = await db.execute_fetchall("SELECT 1 FROM cves WHERE cve_id = ?", (cve_key,))
    if not exists:
        raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

    sector_value = sector.strip()
    sentences, epss_history, related, correlation, momentum, related_news = await asyncio.gather(
        _drawer_db_task(lambda task_db: _drawer_sentences_payload(task_db, cve_key)),
        _drawer_db_task(lambda task_db: get_epss_history(task_db, cve_key, days=30)),
        _drawer_db_task(lambda task_db: _drawer_related_payload(task_db, cve_key, limit=5)),
        _drawer_db_task(
            lambda task_db: get_correlation_for_cve(task_db, cve_key, user_sector=sector_value)
        ),
        _drawer_db_task(lambda task_db: calculate_momentum(cve_key, task_db)),
        get_related_news_for_cve(cve_key, limit=8),
    )
    correlation["provenance"] = derive_correlation_provenance(
        correlation,
        otx_configured=otx_configured_from_env(),
    )
    return {
        "cve_id": cve_key,
        "sentences": sentences,
        "epss_history": epss_history,
        "related": related,
        "related_news": related_news,
        "correlation": correlation,
        "momentum": momentum,
    }


@detail_router.get("/api/cves/{cve_id}/drawer")
async def get_cve_drawer_bundle(
    cve_id: str,
    sector: str = Query(default="", description="User industry sector for correlation actor matching"),
):
    """Aggregate drawer on-open payloads (sentences, EPSS, related, correlation, momentum)."""
    cve_id = require_cve_id(cve_id)
    cve_key = cve_id

    db = await get_db()
    try:
        bundle = await _build_cve_drawer_bundle(db, cve_key, sector=sector)
        await db.commit()
    finally:
        await db.close()

    return bundle


async def _load_cve_detail_from_db(cve_key: str) -> dict:
    """Fast path: DB reads only so the pool connection is not held during I/O."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, cvss_score, severity, published, modified,
                   affected_products, affected_products_source, mitre_technique,
                   summary, is_kev, epss_score, epss_percentile, has_poc, patch_available,
                   has_ai_context, source_urls, cwe_ids, updated_at
            FROM cves
            WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_key} not found")

        cve = row_to_cve_dict(rows[0])
        wl = await get_watchlist_entry(db, cve_key)
        if wl:
            cve["watchlist_state"] = wl["state"]
            cve["watchlist_snooze_until"] = (wl.get("snooze_until") or "").strip() or None
        kev_rows = await db.execute_fetchall(
            """
            SELECT date_added, due_date, vendor_project, vulnerability_name,
                   known_ransomware, cwes, required_action
            FROM kev_deadlines WHERE cve_id = ?
            """,
            (cve_key,),
        )
        if kev_rows:
            kev_row = dict(kev_rows[0])
            cve["kev_date_added"] = (kev_row.get("date_added") or "").strip() or None
            cve["kev_due_date"] = (kev_row.get("due_date") or "").strip() or None
            cve["kev_required_action"] = (
                (kev_row.get("required_action") or "").strip() or None
            )
            cve["kev_vendor_project"] = (kev_row.get("vendor_project") or "").strip() or None
            cve["kev_vulnerability_name"] = (
                kev_row.get("vulnerability_name") or ""
            ).strip() or None
            cve["kev_ransomware_use"] = (
                str(kev_row.get("known_ransomware") or "").strip().lower() == "known"
            )
            try:
                parsed_cwes = json.loads(kev_row.get("cwes") or "[]")
                cve["kev_cwes"] = parsed_cwes if isinstance(parsed_cwes, list) else []
            except (json.JSONDecodeError, TypeError):
                cve["kev_cwes"] = []
        ssvc_cached = await get_feed_cache(db, f"ssvc:{cve_key}", max_age_hours=24 * 365)
        if ssvc_cached and isinstance(ssvc_cached.get("decisions"), dict):
            cve["ssvc"] = ssvc_cached
        cve["techniques"] = await get_techniques_for_cve(db, cve_key)
        cve["atlas_techniques"] = await get_atlas_techniques_for_cve(db, cve_key)
        cve["atlas_case_studies"] = await get_atlas_case_studies_for_cve(db, cve_key)
        return cve
    finally:
        await db.close()


async def _detail_enrich_exploits(cve_key: str, cve: dict) -> dict:
    pending_provenance = {
        "status": "pending",
        "source": "Sploitus + BRIEFR exploit index",
        "as_of": None,
    }
    try:
        db = await get_db()
        try:
            try:
                public_exploits = await load_public_exploits_for_cve(
                    db,
                    cve_key,
                    has_poc=bool(cve.get("has_poc")),
                    source_urls=cve.get("source_urls"),
                )
                provenance = await derive_exploit_provenance(
                    db,
                    cve_key,
                    used_nvd_fallback=bool(public_exploits)
                    and not await get_cve_exploits_latest_fetched_at(db, cve_key)
                    and not await get_feed_cache_timestamp(db, f"sploitus:{cve_key}"),
                )
                await db.commit()
                return {"public_exploits": public_exploits, "exploit_provenance": provenance}
            except Exception as exc:
                logger.error("Sploitus load failed for %s: %s", cve_key, exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                try:
                    provenance = await derive_exploit_provenance(db, cve_key)
                except Exception:
                    provenance = pending_provenance
                return {"public_exploits": [], "exploit_provenance": provenance}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error(
            "Failed to acquire DB or process exploits for %s: %s", cve_key, outer_exc
        )
        return {"public_exploits": [], "exploit_provenance": pending_provenance}


async def _detail_enrich_otx(cve_key: str, otx_key: str) -> dict:
    if not otx_key:
        return {"otx_pulses": []}
    try:
        db = await get_db()
        try:
            try:
                pulses = await load_otx_pulses_for_cve(db, cve_key, otx_key)
                await db.commit()
                return {"otx_pulses": pulses}
            except Exception as exc:
                logger.error("OTX pulse load failed for %s: %s", cve_key, exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                return {"otx_pulses": []}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error("Failed to acquire DB or process OTX for %s: %s", cve_key, outer_exc)
        return {"otx_pulses": []}


async def _detail_enrich_osv(cve_key: str, existing_summary: str | None) -> dict:
    try:
        osv_data = await fetch_osv_by_cve(cve_key)
        out: dict = {"osv_packages": osv_data}
        if not (existing_summary or "").strip():
            for entry in osv_data:
                osv_summary = (entry.get("summary") or "").strip()
                if osv_summary:
                    out["summary"] = osv_summary
                    break
        return out
    except Exception as exc:
        logger.error("OSV lookup failed for %s: %s", cve_key, exc)
        return {"osv_packages": []}


def _circl_enrichment_patch(enriched: dict | None) -> dict:
    """Return only CIRCL-owned fields so concurrent enrichments are not overwritten."""
    if not isinstance(enriched, dict):
        return {}
    patch: dict = {}
    if "circl" in enriched:
        patch["circl"] = enriched["circl"]
    if "capec_ids" in enriched:
        patch["capec_ids"] = enriched["capec_ids"]
    if "source_urls" in enriched:
        patch["source_urls"] = enriched["source_urls"]
    return patch


async def _detail_enrich_circl(cve: dict) -> dict:
    try:
        db = await get_db()
        try:
            try:
                enriched = await enrich_cve_circl(db, dict(cve))
                await db.commit()
                return _circl_enrichment_patch(enriched)
            except Exception as exc:
                logger.error("CIRCL enrichment failed for %s: %s", cve.get("cve_id"), exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                return {}
        finally:
            await db.close()
    except Exception as outer_exc:
        logger.error(
            "Failed to acquire DB or process CIRCL for %s: %s", cve.get("cve_id"), outer_exc
        )
        return {}


@detail_router.get("/api/cves/{cve_id}")
async def get_cve(cve_id: str):
    cve_id = require_cve_id(cve_id)
    cve_key = cve_id

    cve = await _load_cve_detail_from_db(cve_key)

    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    cve["greynoise_configured"] = bool(greynoise_key)
    cve["greynoise_scans"] = []

    otx_key = os.environ.get("OTX_API_KEY", "").strip()
    cve["otx_configured"] = bool(otx_key)

    exploit_patch, otx_patch, osv_patch, circl_patch = await asyncio.gather(
        _detail_enrich_exploits(cve_key, cve),
        _detail_enrich_otx(cve_key, otx_key),
        _detail_enrich_osv(cve_key, cve.get("summary")),
        _detail_enrich_circl(cve),
    )
    cve.update(exploit_patch)
    cve.update(otx_patch)
    cve.update(osv_patch)
    cve.update(circl_patch)

    return cve
