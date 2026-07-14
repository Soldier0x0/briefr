"""Pulse-centric campaign clustering (Correlation v2 Phase 1)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from correlation.config import CAMPAIGN_ALGORITHM_VERSION, get_max_campaign_members
from correlation.lifecycle import (
    _parse_dt,
    compute_campaign_lifecycle,
    fetch_member_lifecycle_inputs,
)
from correlation.hub_suppress import filter_campaign_members
from correlation.pulse_families import (
    campaign_id_for_family,
    legacy_campaign_id_for_pulse,
    rebuild_pulse_families,
)

logger = logging.getLogger(__name__)

CORRELATION_BUILD_WATERMARK_KEY = "correlation_build_watermark"
CORRELATION_LAST_RUN_KEY = "correlation_last_run"


def campaign_id_for_pulse(pulse_id: str) -> str:
    """Legacy per-pulse id — still used for suppression migration (CORR-PR-9)."""
    return legacy_campaign_id_for_pulse(pulse_id)


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


async def _pulse_counts_for_cves(db, cve_ids: list[str]) -> dict[str, int]:
    if not cve_ids:
        return {}
    placeholders = ",".join("?" * len(cve_ids))
    rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, COUNT(DISTINCT pulse_id) AS pulse_count
        FROM otx_cve_pulses
        WHERE cve_id IN ({placeholders})
        GROUP BY cve_id
        """,
        tuple(cve_ids),
    )
    return {row["cve_id"]: int(row["pulse_count"]) for row in rows}


async def build_campaigns_from_pulses(db) -> dict[str, int]:
    """
    Rebuild correlation_campaigns + members from OTX pulses grouped by family.
    One campaign per pulse family (CORR-PR-9); mirrored pulses collapse together.
    """
    from database import set_sync_state_value

    family_stats = await rebuild_pulse_families(db)

    family_pulse_rows = await db.execute_fetchall(
        """
        SELECT pf.family_id, pf.pulse_id, p.pulse_name, p.author, p.created_date,
               p.adversary, p.malware_families, p.tags, p.targeted_countries, p.ioc_count
        FROM pulse_families pf
        LEFT JOIN otx_pulses p ON p.pulse_id = pf.pulse_id
        ORDER BY pf.family_id ASC, p.created_date ASC, pf.pulse_id ASC
        """
    )

    families: dict[str, list[dict]] = {}
    for row in family_pulse_rows:
        families.setdefault(row["family_id"], []).append(dict(row))

    existing_rows = await db.execute_fetchall(
        "SELECT campaign_id, family_id FROM correlation_campaigns WHERE family_id IS NOT NULL"
    )
    old_family_ids = {row["family_id"] for row in existing_rows if row["family_id"]}
    new_family_ids = set(families.keys())
    vanished = old_family_ids - new_family_ids

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    for fam_id in vanished:
        await db.execute(
            """
            UPDATE correlation_campaigns
            SET retracted_at = ?, lifecycle = 'declining'
            WHERE family_id = ? AND retracted_at IS NULL
            """,
            (now, fam_id),
        )

    await db.execute(
        """
        DELETE FROM correlation_campaign_members
        WHERE campaign_id IN (
            SELECT campaign_id FROM correlation_campaigns WHERE retracted_at IS NULL
        )
        """
    )
    await db.execute("DELETE FROM correlation_campaigns WHERE retracted_at IS NULL")

    campaigns_written = 0
    members_written = 0

    for fam_id, pulses in families.items():
        pulse_ids = [p["pulse_id"] for p in pulses if p.get("pulse_id")]
        if not pulse_ids:
            continue

        created_dates = {p["pulse_id"]: p.get("created_date") or "" for p in pulses}
        oldest_pulse = sorted(
            pulse_ids,
            key=lambda pid: (
                _parse_dt(created_dates.get(pid)) or datetime.min.replace(tzinfo=timezone.utc),
                pid,
            ),
        )[0]
        campaign_id = campaign_id_for_family(fam_id, oldest_pulse)

        authors = sorted({
            (p.get("author") or "").strip()
            for p in pulses
            if (p.get("author") or "").strip()
        })
        author_count = max(1, len(authors))

        primary = next(p for p in pulses if p["pulse_id"] == oldest_pulse)
        label = (primary.get("pulse_name") or "OTX pulse").strip() or "OTX pulse"
        adversary = (primary.get("adversary") or "").strip()
        malware = _parse_json_list(primary.get("malware_families"))
        tags = _parse_json_list(primary.get("tags"))
        countries = _parse_json_list(primary.get("targeted_countries"))

        pg = type(db).__name__ == "PostgresConnection"
        member_ph = ",".join(f"${i+1}" if pg else "?" for i in range(len(pulse_ids)))
        member_rows = await db.execute_fetchall(
            f"""
            SELECT DISTINCT ocp.cve_id
            FROM otx_cve_pulses ocp
            INNER JOIN cves c ON c.cve_id = ocp.cve_id
            WHERE ocp.pulse_id IN ({member_ph})
            ORDER BY ocp.cve_id ASC
            """,
            tuple(pulse_ids),
        )
        members = [row["cve_id"] for row in member_rows]
        members = members[: get_max_campaign_members()]
        if len(members) < 2:
            continue

        seen_dates = [
            dt for dt in (_parse_dt(created_dates.get(pid)) for pid in pulse_ids) if dt
        ]
        first_seen = min(seen_dates).isoformat() if seen_dates else (primary.get("created_date") or "")
        last_seen = max(seen_dates).isoformat() if seen_dates else first_seen

        confidence = "medium"
        member_inputs, observation_at = await fetch_member_lifecycle_inputs(
            db, oldest_pulse, members
        )
        lifecycle = compute_campaign_lifecycle(
            pulse_created_date=primary.get("created_date") or "",
            members=member_inputs,
            member_observation_at=observation_at,
            now=now_dt,
        )
        await db.execute(
            """
            INSERT INTO correlation_campaigns (
                campaign_id, primary_pulse_id, label, adversary, malware_families,
                tags, targeted_countries, confidence, member_count, lifecycle,
                campaign_version, computed_at, family_id, first_seen, last_seen,
                independent_sources, author_count, retracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                campaign_id,
                oldest_pulse,
                label,
                adversary,
                json.dumps(malware),
                json.dumps(tags),
                json.dumps(countries),
                confidence,
                len(members),
                lifecycle,
                CAMPAIGN_ALGORITHM_VERSION,
                now,
                fam_id,
                first_seen,
                last_seen,
                1,
                author_count,
            ),
        )
        campaigns_written += 1

        for cve_id in members:
            await db.execute(
                """
                INSERT INTO correlation_campaign_members (campaign_id, cve_id, role)
                VALUES (?, ?, ?)
                """,
                (campaign_id, cve_id, "member"),
            )
            members_written += 1

    await set_sync_state_value(db, CORRELATION_BUILD_WATERMARK_KEY, now)
    await set_sync_state_value(db, CORRELATION_LAST_RUN_KEY, now)
    return {
        "campaigns": campaigns_written,
        "members": members_written,
        "families": family_stats.get("families", 0),
    }


async def prune_invalid_campaign_members(db) -> int:
    """Drop campaign members whose CVE no longer exists."""
    cursor = await db.execute(
        """
        DELETE FROM correlation_campaign_members
        WHERE cve_id NOT IN (SELECT cve_id FROM cves)
        """
    )
    removed = cursor.rowcount or 0

    await db.execute(
        """
        DELETE FROM correlation_campaigns
        WHERE campaign_id NOT IN (
            SELECT DISTINCT campaign_id FROM correlation_campaign_members
        )
        """
    )
    await db.execute(
        """
        UPDATE correlation_campaigns
        SET member_count = (
            SELECT COUNT(*) FROM correlation_campaign_members m
            WHERE m.campaign_id = correlation_campaigns.campaign_id
        )
        """
    )
    return removed


async def get_campaigns_for_cve(
    db, cve_id: str, strong_infra_peers: set[str] | None = None
) -> list[dict]:
    """
    Return campaign clusters containing cve_id with hub filtering applied.
    Clusters are seeded by same-pulse co-tagging (nightly build_campaigns_from_pulses)
    and expanded here with CVEs that share strong indicators (hash/domain) with
    the anchor, even when never co-tagged in the same OTX pulse — strong shared
    evidence shouldn't be siloed into the weaker "infrastructure" bucket.

    `strong_infra_peers` lets a caller that already computed
    find_shared_infrastructure_v2 (e.g. get_correlation_for_cve) pass the
    result through instead of triggering a second, identical query.
    """
    from correlation.attribution import (
        attribution_conflict,
        build_attribution_claims,
        load_mitre_alias_index,
    )
    from correlation.confidence import campaign_confidence
    from correlation.copy import campaign_summary, sanitize_pulse_text
    from correlation.ioc_graph import find_shared_infrastructure_v2, ioc_edges_between, batch_ioc_edges_for_peers
    from correlation.local import kev_exploit_boosters
    from correlation.suppressions import load_suppressions, resolve_suppressed_campaign_ids

    cve_upper = cve_id.upper()
    suppressions = await load_suppressions(db, cve_upper)
    suppressed_campaign_ids = await resolve_suppressed_campaign_ids(db, suppressions)

    if strong_infra_peers is None:
        strong_infra_peers = {
            peer["cve_id_b"]
            for peer in await find_shared_infrastructure_v2(db, cve_upper)
            if peer["shared_hash_count"] or peer["shared_domain_count"]
        }

    rows = await db.execute_fetchall(
        """
        SELECT c.campaign_id, c.primary_pulse_id, c.label, c.adversary,
               c.malware_families, c.tags, c.targeted_countries, c.confidence,
               c.member_count, c.lifecycle, c.campaign_version, c.computed_at,
               c.author_count, c.first_seen, c.last_seen, c.family_id
        FROM correlation_campaigns c
        INNER JOIN correlation_campaign_members m ON m.campaign_id = c.campaign_id
        WHERE m.cve_id = ? AND c.retracted_at IS NULL
        ORDER BY c.member_count DESC, c.label ASC
        """,
        (cve_upper,),
    )

    campaign_ids = [
        r["campaign_id"] for r in rows if r["campaign_id"] not in suppressed_campaign_ids
    ]
    
    # Batch fetch all campaign members for the active campaigns
    campaign_members_map: dict[str, list[str]] = {}
    if campaign_ids:
        pg = type(db).__name__ == "PostgresConnection"
        placeholders = ",".join(f"${i+1}" if pg else "?" for i in range(len(campaign_ids)))
        all_member_rows = await db.execute_fetchall(
            f"""
            SELECT campaign_id, cve_id FROM correlation_campaign_members
            WHERE campaign_id IN ({placeholders})
            ORDER BY cve_id ASC
            """,
            tuple(campaign_ids),
        )
        for r in all_member_rows:
            campaign_members_map.setdefault(r["campaign_id"], []).append(r["cve_id"])

    # Batch fetch pulse counts for all unique CVEs across all campaigns and their peers
    unique_cves = set()
    unique_cves.add(cve_upper)
    for peer in strong_infra_peers:
        unique_cves.add(peer)
    for cid in campaign_ids:
        for m in campaign_members_map.get(cid, []):
            unique_cves.add(m)

    pulse_counts_map = {}
    if unique_cves:
        cve_list = list(unique_cves)
        pg = type(db).__name__ == "PostgresConnection"
        placeholders = ",".join(f"${i+1}" if pg else "?" for i in range(len(cve_list)))
        pulse_count_rows = await db.execute_fetchall(
            f"""
            SELECT cve_id, COUNT(DISTINCT pulse_id) AS pulse_count
            FROM otx_cve_pulses
            WHERE cve_id IN ({placeholders})
            GROUP BY cve_id
            """,
            tuple(cve_list),
        )
        pulse_counts_map = {row["cve_id"]: int(row["pulse_count"]) for row in pulse_count_rows}

    # Batch fetch actor rows for anchor CVE once
    actor_rows = await db.execute_fetchall(
        "SELECT actor_name FROM correlation_actor WHERE cve_id = ?",
        (cve_upper,),
    )
    mitre_names = [r["actor_name"] for r in actor_rows if r["actor_name"]]
    alias_index = await load_mitre_alias_index(db)

    # Collect all unique filtered peer CVEs to batch query their shared IOC edges with anchor
    all_filtered_peers = set()
    campaign_filtered_members = {}
    for row in rows:
        cid = row["campaign_id"]
        if cid in suppressed_campaign_ids:
            continue
        all_members = list(campaign_members_map.get(cid, []))
        for peer in strong_infra_peers:
            if peer not in all_members:
                all_members.append(peer)
        filtered = filter_campaign_members(
            cve_upper, all_members, pulse_counts_map
        )
        if len(filtered) < 2:
            continue
        campaign_filtered_members[cid] = filtered
        for peer in filtered:
            if peer != cve_upper:
                all_filtered_peers.add(peer)

    # Batch fetch shared IOC edges for all filtered peers in one query!
    batch_edges_map = await batch_ioc_edges_for_peers(db, cve_upper, list(all_filtered_peers))

    results: list[dict] = []
    for row in rows:
        cid = row["campaign_id"]
        if cid in suppressed_campaign_ids:
            continue
        filtered = campaign_filtered_members.get(cid)
        if not filtered:
            continue

        ioc_edges = []
        seen_iocs = set()
        for peer in filtered:
            if peer == cve_upper:
                continue
            peer_edges = batch_edges_map.get(peer, [])
            for edge in peer_edges:
                key = (edge.get("ioc_type", ""), edge.get("ioc_value", ""))
                if key in seen_iocs:
                    continue
                seen_iocs.add(key)
                ioc_edges.append(edge)

        confidence, why_not_higher, confidence_factors = campaign_confidence(
            row["confidence"] or "medium",
            ioc_edges,
            has_same_pulse=True,
        )
        safe_label = sanitize_pulse_text(row["label"])

        evidence = [
            {
                "type": "same_pulse",
                "pulse_id": row["primary_pulse_id"],
                "pulse_name": safe_label,
            }
        ]
        for edge in ioc_edges[:5]:
            evidence.append({
                "type": "shared_indicator",
                "ioc_type": edge.get("ioc_type", ""),
                "value": edge.get("ioc_value", ""),
            })

        conflict = attribution_conflict(
            row["adversary"] or "", mitre_names, alias_index=alias_index
        )
        attribution_claims = build_attribution_claims(
            row["adversary"] or "",
            mitre_names,
            alias_index=alias_index,
            otx_observed_at=(row["first_seen"] if row["first_seen"] else "") or "",
        )
        if conflict:
            confidence = "medium" if confidence == "high" else confidence
            why_not_higher = "Adversary attribution conflicts with MITRE technique-matched actors"
            confidence_factors.append({
                "factor": "attribution_conflict",
                "reason": why_not_higher,
            })

        # CORR-PR-4: KEV/exploit status is a priority signal, not a confidence
        # signal (§7) -- a peer being KEV-listed doesn't make the *link*
        # between it and this CVE more certain. Still surfaced as evidence;
        # priority.py's campaign contribution is where it moves the needle.
        boosters = await kev_exploit_boosters(db, filtered, cve_upper)
        if boosters["kev"]:
            evidence.append({
                "type": "kev_booster",
                "members": boosters["kev"][:5],
            })
        elif boosters["exploit"]:
            evidence.append({
                "type": "exploit_booster",
                "members": boosters["exploit"][:5],
            })

        results.append({
            "campaign_id": row["campaign_id"],
            "label": safe_label,
            "primary_pulse_id": row["primary_pulse_id"],
            "adversary": sanitize_pulse_text(row["adversary"] or "", 120),
            "malware_families": _parse_json_list(row["malware_families"]),
            "tags": _parse_json_list(row["tags"]),
            "targeted_countries": _parse_json_list(row["targeted_countries"]),
            "members": filtered,
            "member_count": len(filtered),
            "confidence": confidence,
            "lifecycle": row["lifecycle"] or "active",
            "boosters": boosters,
            "evidence": evidence,
            "summary": campaign_summary(
                safe_label,
                len(filtered) - 1,
                has_ioc=bool(ioc_edges),
            ),
            "sources": ["otx"],
            "why_not_higher": why_not_higher,
            "confidence_factors": confidence_factors,
            "attribution_conflict": conflict,
            "attribution_claims": attribution_claims,
            "attribution_disclaimer": "OTX community pulse — unverified attribution",
            "author_count": int(row["author_count"] or 1),
            "first_seen": row["first_seen"] or "",
            "last_seen": row["last_seen"] or "",
            "family_id": row["family_id"] or "",
        })

    return results
