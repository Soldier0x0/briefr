"""
BRIEFR Correlation Engine v1
Three levels of CVE correlation analysis — all DB-backed, no external API calls
at on-demand time (external data is pre-cached by the nightly OTX job).

Level 1 — Infrastructure: shared exploitation IPs across OTX pulses.
Level 2 — Actor/Sector: ATT&CK groups using this CVE's techniques vs user sector.
Level 3 — Temporal: vendor CVE volume spikes (nightly-only, pre-computed).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

from correlation.config import ENGINE_VERSION, get_correlation_cache_hours, get_otx_ioc_sync_max_per_run

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


def _confidence_from_ip_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def extract_sectors_from_text(text: str) -> list[str]:
    """Keyword-match SECTOR_KEYWORDS against a free-text description."""
    lower = (text or "").lower()
    matched = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(sector)
    return matched


# ── Level 1 — Infrastructure Correlation ─────────────────

async def find_shared_infrastructure(db, cve_id: str) -> list[dict]:
    """
    Find CVEs that share exploitation IPs with cve_id via OTX pulse IOCs.
    Uses data already in otx_pulse_iocs (pre-cached by nightly OTX job).
    Returns list of {cve_id_b, shared_ip_count, confidence}.
    """
    cve_upper = cve_id.upper()

    shared_rows = await db.execute_fetchall(
        """
        SELECT ocp2.cve_id, COUNT(DISTINCT oi2.ioc_value) AS shared_ip_count
        FROM otx_pulse_iocs oi2
        JOIN otx_cve_pulses ocp2 ON ocp2.pulse_id = oi2.pulse_id
        WHERE oi2.ioc_value IN (
            SELECT DISTINCT oi.ioc_value
            FROM otx_cve_pulses ocp
            JOIN otx_pulse_iocs oi ON oi.pulse_id = ocp.pulse_id
            WHERE ocp.cve_id = ?
              AND UPPER(oi.ioc_type) IN ('IPV4', 'IPV6', 'IP')
        )
          AND UPPER(oi2.ioc_type) IN ('IPV4', 'IPV6', 'IP')
          AND ocp2.cve_id != ?
        GROUP BY ocp2.cve_id
        ORDER BY shared_ip_count DESC
        LIMIT 20
        """,
        (cve_upper, cve_upper),
    )

    results = []
    for row in shared_rows:
        count = row["shared_ip_count"]
        results.append({
            "cve_id_b": row["cve_id"],
            "shared_ip_count": count,
            "confidence": _confidence_from_ip_count(count),
        })
    return results


async def _store_infrastructure_correlation(db, cve_id: str, findings: list[dict]) -> None:
    await db.execute(
        "DELETE FROM correlation_infrastructure WHERE cve_id_a = ?",
        (cve_id.upper(),),
    )
    for f in findings:
        await db.execute(
            """
            INSERT INTO correlation_infrastructure
                (cve_id_a, cve_id_b, shared_ip_count, confidence, detected_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(cve_id_a, cve_id_b) DO UPDATE SET
                shared_ip_count = excluded.shared_ip_count,
                confidence      = excluded.confidence,
                detected_at     = excluded.detected_at
            """,
            (cve_id.upper(), f["cve_id_b"], f["shared_ip_count"], f["confidence"]),
        )


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

    # Path 1: MITRE groups linked via technique mapping
    tech_rows = await db.execute_fetchall(
        "SELECT technique_id FROM cve_technique_map WHERE cve_id = ?",
        (cve_upper,),
    )
    technique_ids = [r["technique_id"] for r in tech_rows]

    if technique_ids:
        placeholders = ",".join("?" * len(technique_ids))
        group_rows = await db.execute_fetchall(
            f"""
            SELECT DISTINCT mg.group_id, mg.name, mg.sectors
            FROM group_technique_map gtm
            JOIN mitre_groups mg ON mg.group_id = gtm.group_id
            WHERE gtm.technique_id IN ({placeholders})
            ORDER BY mg.name
            LIMIT 10
            """,
            technique_ids,
        )
        for row in group_rows:
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
                "confidence": "medium",
                "source": "mitre_attack",
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
    await db.execute(
        "DELETE FROM correlation_actor WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    for f in findings:
        await db.execute(
            """
            INSERT INTO correlation_actor
                (cve_id, actor_name, actor_sectors, user_sector_match, confidence, detected_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
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
            ),
        )


# ── Level 3 — Temporal Volume Anomaly ────────────────────

async def find_temporal_anomalies(db) -> list[dict]:
    """
    Detect vendors with unusual CVE publication volume this week vs 90-day baseline.
    Anomaly score = current_week / average_weekly; flag if ≥ 3.0.
    Returns list of {vendor, current_week_count, average_weekly_count, anomaly_score}.
    """
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, affected_products, published
        FROM cves
        WHERE datetime(published) >= datetime('now', '-90 days')
          AND affected_products IS NOT NULL
          AND affected_products != '[]'
        """,
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
    await db.execute("DELETE FROM correlation_temporal WHERE 1=1")
    for a in anomalies:
        await db.execute(
            """
            INSERT INTO correlation_temporal
                (vendor, current_week_count, average_weekly_count, anomaly_score, detected_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (
                a["vendor"],
                a["current_week_count"],
                a["average_weekly_count"],
                a["anomaly_score"],
            ),
        )


async def _get_temporal_for_cve(db, cve_id: str) -> list[dict]:
    """Return pre-computed temporal anomalies matching this CVE's vendors."""
    row = await db.execute_fetchall(
        "SELECT affected_products FROM cves WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    if not row:
        return []

    products = _parse_json_list(row[0]["affected_products"])
    vendors = {
        str(p).split(":")[0].lower().strip()
        for p in products
        if ":" in str(p)
    }
    vendors.discard("")
    if not vendors:
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
    Runs Level 1 + Level 2 live; Level 3 uses pre-computed nightly data.
    v2: includes pulse-centric campaign clusters when built by nightly job.
    """
    from database import get_feed_cache, set_feed_cache
    from correlation.campaigns import get_campaigns_for_cve

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
        campaigns = await get_campaigns_for_cve(db, cve_upper)

        await _store_infrastructure_correlation(db, cve_upper, infrastructure)
        await _store_actor_correlation(db, cve_upper, actor)

        if campaigns:
            otx_status = "ok"
        elif otx_configured:
            otx_status = "ok"
        else:
            otx_status = "not_configured"

        result = {
            "cve_id": cve_upper,
            "campaigns": campaigns,
            "infrastructure": infrastructure,
            "actor": actor,
            "temporal": temporal,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "otx_status": otx_status,
            "meta": {
                "engine_version": ENGINE_VERSION,
                "cache_hit": False,
            },
        }
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
            "otx_status": "degraded",
            "error": str(exc),
            "meta": {"engine_version": ENGINE_VERSION},
        }


# ── Nightly batch job ─────────────────────────────────────

async def run_nightly_correlation(db) -> dict:
    """
    Nightly: Run all three correlation levels + v2 campaign rebuild.
    Level 3 runs once globally; Levels 1+2 run per recently-modified CVE.
    Also pre-warms OTX pulse IOCs for recently-active pulses.
    """
    from database import delete_feed_cache_prefix, get_recent_cve_ids_for_otx
    from correlation.campaigns import build_campaigns_from_pulses, prune_invalid_campaign_members

    stats = {
        "cves_processed": 0,
        "infrastructure_pairs": 0,
        "actor_findings": 0,
        "temporal_anomalies": 0,
        "campaigns_built": 0,
        "campaign_members": 0,
        "pruned_members": 0,
    }

    # Level 3: global vendor volume anomaly detection
    try:
        temporal = await find_temporal_anomalies(db)
        await _store_temporal_anomalies(db, temporal)
        stats["temporal_anomalies"] = len(temporal)
        logger.info("Temporal anomalies: %d vendors flagged", len(temporal))
    except Exception as exc:
        logger.error("Level 3 temporal correlation failed: %s", exc)

    stats["pruned_members"] = await prune_invalid_campaign_members(db)

    # Level 1 + 2: per-CVE for recent CVEs
    cve_ids = await get_recent_cve_ids_for_otx(db, days=7)
    for cve_id in cve_ids:
        try:
            infra = await find_shared_infrastructure(db, cve_id)
            if infra:
                await _store_infrastructure_correlation(db, cve_id, infra)
                stats["infrastructure_pairs"] += len(infra)

            actor = await find_actor_sector_correlation(db, cve_id)
            if actor:
                await _store_actor_correlation(db, cve_id, actor)
                stats["actor_findings"] += len(actor)

            stats["cves_processed"] += 1
        except Exception as exc:
            logger.warning("Nightly correlation skip %s: %s", cve_id, exc)

    try:
        campaign_stats = await build_campaigns_from_pulses(db)
        stats["campaigns_built"] = campaign_stats.get("campaigns", 0)
        stats["campaign_members"] = campaign_stats.get("members", 0)
    except Exception as exc:
        logger.error("Campaign build failed: %s", exc)

    await delete_feed_cache_prefix(db, "correlation:v2:")
    await delete_feed_cache_prefix(db, "correlation:v1:")

    await db.commit()
    logger.info(
        "Nightly correlation done: %d CVEs, %d infra pairs, %d actors, %d anomalies, "
        "%d campaigns (%d members)",
        stats["cves_processed"],
        stats["infrastructure_pairs"],
        stats["actor_findings"],
        stats["temporal_anomalies"],
        stats["campaigns_built"],
        stats["campaign_members"],
    )
    return stats


async def prefetch_pulse_iocs_for_nightly(
    db, api_key: str, max_pulses: int | None = None
) -> int:
    """
    Pre-fetch IOC data for pulses not yet in otx_pulse_iocs.
    Called by the nightly OTX + correlation job so Level 1 has IP data.
    """
    from feeds.otx import fetch_pulse_iocs
    from database import store_otx_pulse_iocs

    if not api_key:
        return 0

    if max_pulses is None:
        max_pulses = get_otx_ioc_sync_max_per_run()

    missing_rows = await db.execute_fetchall(
        """
        SELECT DISTINCT ocp.pulse_id,
               CASE WHEN EXISTS (
                   SELECT 1 FROM otx_cve_pulses p2
                   JOIN cves c ON c.cve_id = p2.cve_id
                   WHERE p2.pulse_id = ocp.pulse_id
                     AND (COALESCE(c.is_kev, 0) = 1 OR COALESCE(c.has_poc, 0) = 1)
               ) THEN 0 ELSE 1 END AS priority_rank
        FROM otx_cve_pulses ocp
        WHERE NOT EXISTS (
            SELECT 1 FROM otx_pulse_iocs opi WHERE opi.pulse_id = ocp.pulse_id
        )
        ORDER BY priority_rank ASC, ocp.fetched_at DESC
        LIMIT ?
        """,
        (max_pulses,),
    )

    fetched = 0
    for row in missing_rows:
        pulse_id = row["pulse_id"]
        try:
            iocs = await fetch_pulse_iocs(pulse_id, api_key)
            if iocs:
                await store_otx_pulse_iocs(db, pulse_id, iocs)
                fetched += 1
        except Exception as exc:
            logger.warning("IOC prefetch failed for pulse %s: %s", pulse_id, exc)
    return fetched
