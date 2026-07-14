"""
BRIEFR Correlation Engine v2
CVE correlation analysis — DB-backed, no external API calls at on-demand time
(external data is pre-cached by the nightly OTX job).

Campaigns — pulse-seeded clusters expanded on-demand by shared strong IOCs
            (ioc_graph.py); see correlation/campaigns.py.
Infrastructure — weaker shared-IOC peers that don't qualify for a campaign.
Actor/Sector — ATT&CK groups using this CVE's techniques vs user sector.
Temporal — vendor CVE volume spikes (nightly-only, pre-computed).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from db.timeutil import utcnow_str

logger = logging.getLogger(__name__)

from correlation.config import (
    ENGINE_VERSION,
    get_correlation_cache_hours,
    get_mitre_min_overlap,
    get_otx_ioc_sync_max_per_run,
)

# Sector keyword mapping for actor description parsing
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Technology": ["technology", "tech company", "software", "semiconductor", "internet", "cloud", "saas", "it services"],
    "Finance": ["financial", "finance", "banking", "bank", "insurance", "investment", "trading", "cryptocurrency", "fintech"],
    "Healthcare": ["healthcare", "health care", "medical", "hospital", "pharmaceutical", "pharma", "biotech", "life sciences"],
    "Government": ["government", "government agency", "public sector", "defense", "military", "intelligence", "espionage", "nation-state", "national security"],
    "Energy": ["energy", "oil", "gas", "electricity", "power grid", "utilities", "nuclear", "pipeline", "petrochemical"],
    "Manufacturing": ["manufacturing", "industrial", "ics", "scada", "critical infrastructure", "supply chain", "automotive"],
    "Retail": ["retail", "e-commerce", "consumer goods", "commerce", "hospitality", "restaurant"],
    "Telecommunications": ["telecom", "telecommunications", "isp", "carrier", "mobile operator", "internet provider"],
    "Education": ["education", "academic", "university", "research institution", "think tank"],
    "Transportation": ["transportation", "aviation", "airline", "shipping", "logistics", "maritime", "railway"],
    "Media": ["media", "news", "journalism", "entertainment", "broadcast", "publishing"],
}


# ── Utilities ─────────────────────────────────────────────

def _parse_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def extract_sectors_from_text(text: str) -> list[str]:
    """Keyword-match SECTOR_KEYWORDS against a free-text description."""
    lower = (text or "").lower()
    matched = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(sector)
    return matched


# ── Level 2 — Actor / Sector Correlation ─────────────────

async def find_actor_sector_correlation(
    db, cve_id: str, user_sector: str = ""
) -> list[dict]:
    """
    Find ATT&CK groups that use this CVE's techniques, matched against user sector.
    Also surfaces OTX pulse adversary attributions as lower-confidence signals.
    Returns list of {actor_name, actor_sectors, user_sector_match, confidence, source}.
    """
    cve_upper = cve_id.upper()
    user_sector_lower = user_sector.lower()

    results: list[dict] = []
    seen: set[str] = set()

    # Path 1: MITRE groups linked via technique mapping, scored by technique
    # overlap (|CVE techniques ∩ group techniques| / |CVE techniques|) rather
    # than "any shared technique" — a single shared technique out of dozens
    # used to score the same as a strong match.
    tech_rows = await db.execute_fetchall(
        "SELECT technique_id FROM cve_technique_map WHERE cve_id = ?",
        (cve_upper,),
    )
    technique_ids = list({r["technique_id"] for r in tech_rows if r["technique_id"]})

    if technique_ids:
        placeholders = ",".join("?" * len(technique_ids))
        group_rows = await db.execute_fetchall(
            f"""
            SELECT mg.group_id, mg.name, mg.sectors,
                   COUNT(DISTINCT gtm.technique_id) AS matched
            FROM group_technique_map gtm
            JOIN mitre_groups mg ON mg.group_id = gtm.group_id
            WHERE gtm.technique_id IN ({placeholders})
            GROUP BY mg.group_id
            """,
            technique_ids,
        )
        min_overlap = get_mitre_min_overlap()
        scored = []
        for row in group_rows:
            overlap = row["matched"] / len(technique_ids)
            if overlap >= min_overlap:
                scored.append((overlap, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        for overlap, row in scored[:3]:
            name = row["name"]
            if name in seen:
                continue
            seen.add(name)
            actor_sectors = _parse_json_list(row["sectors"])
            sector_match = bool(
                user_sector_lower and
                any(
                    user_sector_lower in s.lower() or s.lower() in user_sector_lower
                    for s in actor_sectors
                )
            )
            results.append({
                "actor_name": name,
                "actor_sectors": actor_sectors,
                "user_sector_match": sector_match,
                "confidence": "medium" if overlap >= 0.5 else "low",
                "source": "mitre_attack",
                "technique_overlap": round(overlap, 2),
            })

    # Path 2: OTX pulse adversary attributions
    otx_rows = await db.execute_fetchall(
        """
        SELECT DISTINCT adversary
        FROM otx_cve_pulses
        WHERE cve_id = ? AND adversary != ''
        """,
        (cve_upper,),
    )
    for row in otx_rows:
        adversary = (row["adversary"] or "").strip()
        if not adversary or adversary in seen:
            continue
        seen.add(adversary)
        results.append({
            "actor_name": adversary,
            "actor_sectors": [],
            "user_sector_match": False,
            "confidence": "low",
            "source": "otx_pulse",
        })

    return results


async def _store_actor_correlation(
    db, cve_id: str, findings: list[dict]
) -> None:
    now = utcnow_str()
    await db.execute(
        "DELETE FROM correlation_actor WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    for f in findings:
        await db.execute(
            """
            INSERT INTO correlation_actor
                (cve_id, actor_name, actor_sectors, user_sector_match, confidence, detected_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cve_id, actor_name) DO UPDATE SET
                actor_sectors     = excluded.actor_sectors,
                user_sector_match = excluded.user_sector_match,
                confidence        = excluded.confidence,
                detected_at       = excluded.detected_at
            """,
            (
                cve_id.upper(),
                f["actor_name"],
                json.dumps(f["actor_sectors"]),
                1 if f["user_sector_match"] else 0,
                f["confidence"],
                now,
            ),
        )


# ── Level 3 — Temporal Volume Anomaly ────────────────────

async def find_temporal_anomalies(db) -> list[dict]:
    """
    Detect vendors with unusual CVE publication volume this week vs 90-day baseline.
    Anomaly score = current_week / average_weekly; flag if ≥ 3.0.
    Returns list of {vendor, current_week_count, average_weekly_count, anomaly_score}.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, affected_products, published
        FROM cves
        WHERE published IS NOT NULL
          AND published != ''
          AND published >= ?
          AND affected_products IS NOT NULL
          AND affected_products != '[]'
        """,
        (cutoff,),
    )

    now_utc = datetime.now(timezone.utc)
    week_ago = now_utc - timedelta(days=7)

    vendor_week: dict[str, int] = {}
    vendor_total: dict[str, int] = {}

    for row in rows:
        products = _parse_json_list(row["affected_products"])
        published_str = (row["published"] or "").strip()

        try:
            pub = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            is_recent = pub >= week_ago
        except Exception:
            is_recent = False

        seen_vendors: set[str] = set()
        for prod in products:
            prod_str = str(prod)
            if ":" not in prod_str:
                continue
            vendor = prod_str.split(":")[0].lower().strip()
            if not vendor or vendor in seen_vendors:
                continue
            seen_vendors.add(vendor)
            vendor_total[vendor] = vendor_total.get(vendor, 0) + 1
            if is_recent:
                vendor_week[vendor] = vendor_week.get(vendor, 0) + 1

    anomalies = []
    weeks_in_window = 90.0 / 7.0
    for vendor, week_count in vendor_week.items():
        total = vendor_total.get(vendor, week_count)
        avg_weekly = total / weeks_in_window
        if avg_weekly < 0.5:
            continue
        score = week_count / avg_weekly
        if score >= 3.0:
            anomalies.append({
                "vendor": vendor,
                "current_week_count": week_count,
                "average_weekly_count": round(avg_weekly, 2),
                "anomaly_score": round(score, 2),
            })

    anomalies.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return anomalies[:20]


async def _store_temporal_anomalies(db, anomalies: list[dict]) -> None:
    now = utcnow_str()
    await db.execute("DELETE FROM correlation_temporal WHERE 1=1")
    for a in anomalies:
        await db.execute(
            """
            INSERT INTO correlation_temporal
                (vendor, current_week_count, average_weekly_count, anomaly_score, detected_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                a["vendor"],
                a["current_week_count"],
                a["average_weekly_count"],
                a["anomaly_score"],
                now,
            ),
        )


async def _get_temporal_for_cve(db, cve_id: str) -> list[dict]:
    """Return pre-computed temporal anomalies matching this CVE's vendors.

    Gated per §15: a vendor-volume spike is only useful to an analyst if it's
    on their stack, or the CVE itself already carries a KEV/exploit signal —
    otherwise it's an academic stat about an unrelated vendor.
    """
    from correlation.local import cve_matches_stack, stack_terms_list

    row = await db.execute_fetchall(
        "SELECT affected_products, description, is_kev, has_poc FROM cves WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    if not row:
        return []

    cve_row = row[0]
    products = _parse_json_list(cve_row["affected_products"])
    vendors = {
        str(p).split(":")[0].lower().strip()
        for p in products
        if ":" in str(p)
    }
    vendors.discard("")
    if not vendors:
        return []

    terms = stack_terms_list()
    on_stack = cve_matches_stack(cve_id, cve_row["description"] or "", products, terms)
    has_signal = bool(cve_row["is_kev"]) or bool(cve_row["has_poc"])
    if terms and not on_stack and not has_signal:
        return []

    results = []
    for vendor in vendors:
        anomaly_rows = await db.execute_fetchall(
            """
            SELECT vendor, current_week_count, average_weekly_count, anomaly_score
            FROM correlation_temporal
            WHERE vendor = ?
            """,
            (vendor,),
        )
        for r in anomaly_rows:
            results.append(dict(r))
    return results


# ── On-demand entry point (with 6-hour cache) ─────────────

async def get_correlation_for_cve(
    db,
    cve_id: str,
    user_sector: str = "",
    cache_hours: float | None = None,
) -> dict:
    """
    Return correlation findings for a single CVE with a 6-hour cache.
    Campaigns/infrastructure/actor are computed live; temporal anomalies use
    pre-computed nightly data. Includes a combined priority score.
    """
    from database import get_feed_cache, set_feed_cache
    from correlation.campaigns import get_campaigns_for_cve
    from correlation.priority import compute_correlation_priority

    if cache_hours is None:
        cache_hours = get_correlation_cache_hours()

    cve_upper = cve_id.upper()
    cache_key = f"correlation:v2:{cve_upper}:{user_sector}"

    cached = await get_feed_cache(db, cache_key, cache_hours)
    if cached is not None:
        return cached

    import os
    otx_configured = bool(os.environ.get("OTX_API_KEY", "").strip())

    try:
        from correlation.ioc_graph import find_shared_infrastructure_v2
        from correlation.suppressions import (
            is_infrastructure_suppressed,
            load_suppressions,
        )

        suppressions = await load_suppressions(db, cve_upper)
        infrastructure = await find_shared_infrastructure_v2(db, cve_upper)
        infrastructure = [
            row for row in infrastructure
            if not is_infrastructure_suppressed(suppressions, row["cve_id_b"])
        ]
        actor = await find_actor_sector_correlation(db, cve_upper, user_sector)
        temporal = await _get_temporal_for_cve(db, cve_upper)

        # Reuse the infrastructure rows already fetched above instead of
        # having get_campaigns_for_cve run find_shared_infrastructure_v2
        # again — also ensures suppressed infra peers aren't promoted into
        # campaign membership, since `infrastructure` here is already
        # suppression-filtered.
        strong_infra_peers = {
            row["cve_id_b"]
            for row in infrastructure
            if row["shared_hash_count"] or row["shared_domain_count"]
        }
        campaigns = await get_campaigns_for_cve(
            db, cve_upper, strong_infra_peers=strong_infra_peers
        )

        # Exclude infrastructure peers already promoted into a campaign above
        # (strong shared IOCs) so campaigns and infrastructure are
        # non-overlapping tiers rather than two views of the same data.
        campaign_members = {m for c in campaigns for m in c.get("members", [])}
        infrastructure = [
            row for row in infrastructure
            if row["cve_id_b"] not in campaign_members
        ]

        await _store_actor_correlation(db, cve_upper, actor)

        if campaigns:
            otx_status = "ok"
        elif otx_configured:
            otx_status = "ok"
        else:
            otx_status = "not_configured"

        boosters = {
            "kev": sorted({cve for c in campaigns for cve in (c.get("boosters") or {}).get("kev", [])}),
            "exploit": sorted({cve for c in campaigns for cve in (c.get("boosters") or {}).get("exploit", [])}),
        }

        result = {
            "cve_id": cve_upper,
            "campaigns": campaigns,
            "infrastructure": infrastructure,
            "actor": actor,
            "temporal": temporal,
            "boosters": boosters,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "otx_status": otx_status,
            "meta": {
                "engine_version": ENGINE_VERSION,
                "cache_hit": False,
            },
        }
        result["priority"] = compute_correlation_priority(result)
        await set_feed_cache(db, cache_key, result)
        return result

    except Exception as exc:
        logger.error("Correlation engine failed for %s: %s", cve_id, exc)
        return {
            "cve_id": cve_id.upper(),
            "campaigns": [],
            "infrastructure": [],
            "actor": [],
            "temporal": [],
            "boosters": {"kev": [], "exploit": []},
            "otx_status": "degraded",
            "error": "correlation_unavailable",
            "priority": {"score": 0, "components": []},
            "meta": {"engine_version": ENGINE_VERSION},
        }


async def _recover_db_transaction(db) -> None:
    """Postgres aborts the whole transaction after any failed statement."""
    rollback = getattr(db, "rollback", None)
    if rollback is not None:
        try:
            await rollback()
        except Exception as exc:
            logger.warning("Failed to rollback transaction during recovery: %s", exc)


# ── Nightly batch job ─────────────────────────────────────

async def run_nightly_correlation(db, progress_cb=None) -> dict:
    """
    Nightly: Run all three correlation levels + v2 campaign rebuild.
    Level 3 runs once globally; Levels 1+2 run per recently-modified CVE.
    Also pre-warms OTX pulse IOCs for recently-active pulses.
    """
    from database import delete_feed_cache_prefix, get_recent_cve_ids_for_otx
    from correlation.campaigns import build_campaigns_from_pulses, prune_invalid_campaign_members
    from db.correlation import rebuild_ioc_degree

    stats = {
        "cves_processed": 0,
        "infrastructure_pairs": 0,
        "actor_findings": 0,
        "temporal_anomalies": 0,
        "campaigns_built": 0,
        "campaign_members": 0,
        "pruned_members": 0,
        "ioc_degree_rows": 0,
    }

    # CORR-PR-3: rebuild ioc_degree first so this run's infra edges (computed
    # on-demand, see ioc_graph.find_shared_infrastructure_v2) use fresh counts.
    if progress_cb:
        progress_cb("Rebuilding IOC degree table for hub-penalized confidence…")
    try:
        stats["ioc_degree_rows"] = await rebuild_ioc_degree(db)
    except Exception as exc:
        logger.error(
            "ioc_degree rebuild failed: %s",
            exc,
            extra={"correlation_phase": "ioc_degree_rebuild"},
        )
        await _recover_db_transaction(db)

    # Level 3: global vendor volume anomaly detection
    if progress_cb:
        progress_cb("Level 3: detecting vendor volume temporal anomalies across CVE timeline…")
    try:
        temporal = await find_temporal_anomalies(db)
        await _store_temporal_anomalies(db, temporal)
        stats["temporal_anomalies"] = len(temporal)
        logger.info("Temporal anomalies: %d vendors flagged", len(temporal))
    except Exception as exc:
        logger.error(
            "Level 3 temporal correlation failed: %s",
            exc,
            extra={"correlation_phase": "level3_temporal"},
        )
        await _recover_db_transaction(db)

    stats["pruned_members"] = await prune_invalid_campaign_members(db)

    # Actor/sector: per-CVE for recent CVEs (infrastructure is computed
    # on-demand only — see ioc_graph.find_shared_infrastructure_v2)
    cve_ids = await get_recent_cve_ids_for_otx(db, days=7)
    for index, cve_id in enumerate(cve_ids):
        if progress_cb:
            progress_cb(f"Level 1/2: actor & sector correlation for {cve_id} ({index + 1}/{len(cve_ids)} recent CVEs)…")
        try:
            actor = await find_actor_sector_correlation(db, cve_id)
            if actor:
                await _store_actor_correlation(db, cve_id, actor)
                stats["actor_findings"] += len(actor)

            stats["cves_processed"] += 1
        except Exception as exc:
            logger.warning("Nightly correlation skip %s: %s", cve_id, exc)
            await _recover_db_transaction(db)

    if progress_cb:
        progress_cb("Building threat actor campaigns from OTX pulse clusters…")
    try:
        campaign_stats = await build_campaigns_from_pulses(db)
        stats["campaigns_built"] = campaign_stats.get("campaigns", 0)
        stats["campaign_members"] = campaign_stats.get("members", 0)
    except Exception as exc:
        logger.error(
            "Campaign build failed: %s",
            exc,
            extra={"correlation_phase": "campaign_build"},
        )
        await _recover_db_transaction(db)

    if progress_cb:
        progress_cb("Snapshotting correlation quality metrics…")
    try:
        from correlation.metrics import snapshot_correlation_metrics

        metrics_row = await snapshot_correlation_metrics(db)
        stats["metrics_day"] = metrics_row.get("day")
        stats["confirmation_rate"] = metrics_row.get("confirmation_rate")
    except Exception as exc:
        logger.error(
            "Correlation metrics snapshot failed: %s",
            exc,
            extra={"correlation_phase": "metrics_snapshot"},
        )
        await _recover_db_transaction(db)

    await delete_feed_cache_prefix(db, "correlation:v2:")
    await delete_feed_cache_prefix(db, "correlation:v1:")

    await db.commit()
    logger.info(
        "Nightly correlation done: %d CVEs, %d infra pairs, %d actors, %d anomalies, "
        "%d campaigns (%d members), %d ioc_degree rows",
        stats["cves_processed"],
        stats["infrastructure_pairs"],
        stats["actor_findings"],
        stats["temporal_anomalies"],
        stats["campaigns_built"],
        stats["campaign_members"],
        stats["ioc_degree_rows"],
    )
    return stats


async def prefetch_pulse_iocs_for_nightly(
    api_key: str, max_pulses: int | None = None
) -> int:
    """
    Pre-fetch IOC data for pulses not yet in otx_pulse_iocs.
    Called by the nightly OTX + correlation job so Level 1 has IP data.
    """
    from database import get_db, store_otx_pulse_iocs
    from feeds.otx import fetch_pulse_iocs

    if not api_key:
        return 0

    if max_pulses is None:
        max_pulses = get_otx_ioc_sync_max_per_run()

    db = await get_db()
    try:
        missing_rows = await db.execute_fetchall(
            """
        SELECT ocp.pulse_id,
               MAX(ocp.fetched_at) AS max_fetched_at,
               MIN(CASE WHEN EXISTS (
                   SELECT 1 FROM otx_cve_pulses p2
                   JOIN cves c ON c.cve_id = p2.cve_id
                   WHERE p2.pulse_id = ocp.pulse_id
                     AND (COALESCE(c.is_kev, 0) = 1 OR COALESCE(c.has_poc, 0) = 1)
               ) THEN 0 ELSE 1 END) AS priority_rank
        FROM otx_cve_pulses ocp
        WHERE NOT EXISTS (
            SELECT 1 FROM otx_pulse_iocs opi WHERE opi.pulse_id = ocp.pulse_id
        )
        GROUP BY ocp.pulse_id
        ORDER BY priority_rank ASC, max_fetched_at DESC
        LIMIT ?
        """,
            (max_pulses,),
        )
    finally:
        await db.close()

    fetched = 0
    for row in missing_rows:
        pulse_id = row["pulse_id"]
        try:
            iocs = await fetch_pulse_iocs(pulse_id, api_key)
            if not iocs:
                continue
            db = await get_db()
            try:
                await store_otx_pulse_iocs(db, pulse_id, iocs)
                await db.commit()
                fetched += 1
            finally:
                await db.close()
        except Exception as exc:
            logger.warning("IOC prefetch failed for pulse %s: %s", pulse_id, exc)
    return fetched
