"""Pulse-centric campaign clustering (Correlation v2 Phase 1)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from correlation.config import CAMPAIGN_ALGORITHM_VERSION, get_max_campaign_members
from correlation.hub_suppress import filter_campaign_members

logger = logging.getLogger(__name__)

CORRELATION_BUILD_WATERMARK_KEY = "correlation_build_watermark"
CORRELATION_LAST_RUN_KEY = "correlation_last_run"


def campaign_id_for_pulse(pulse_id: str) -> str:
    digest = hashlib.sha256(pulse_id.encode()).hexdigest()[:12]
    return f"camp_{digest}"


def _confidence_for_pulse(member_count: int) -> str:
    if member_count >= 4:
        return "high"
    if member_count >= 2:
        return "medium"
    return "low"


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
    Rebuild correlation_campaigns + members from otx_cve_pulses / otx_pulses.
    One campaign per pulse that links 2+ CVEs.
    """
    from database import set_sync_state_value

    pulse_rows = await db.execute_fetchall(
        """
        SELECT ocp.pulse_id,
               COUNT(DISTINCT ocp.cve_id) AS member_count
        FROM otx_cve_pulses ocp
        INNER JOIN cves c ON c.cve_id = ocp.cve_id
        GROUP BY ocp.pulse_id
        HAVING member_count >= 2
        """
    )

    await db.execute("DELETE FROM correlation_campaign_members")
    await db.execute("DELETE FROM correlation_campaigns")

    campaigns_written = 0
    members_written = 0
    now = datetime.now(timezone.utc).isoformat()

    for prow in pulse_rows:
        pulse_id = prow["pulse_id"]
        campaign_id = campaign_id_for_pulse(pulse_id)

        meta_rows = await db.execute_fetchall(
            """
            SELECT p.pulse_name, p.author, p.created_date, p.adversary,
                   p.malware_families, p.tags, p.targeted_countries, p.ioc_count,
                   ocp.pulse_name AS link_pulse_name, ocp.adversary AS link_adversary,
                   ocp.malware_families AS link_malware, ocp.tags AS link_tags,
                   ocp.targeted_countries AS link_countries
            FROM otx_cve_pulses ocp
            LEFT JOIN otx_pulses p ON p.pulse_id = ocp.pulse_id
            WHERE ocp.pulse_id = ?
            LIMIT 1
            """,
            (pulse_id,),
        )
        meta = dict(meta_rows[0]) if meta_rows else {}

        label = (
            (meta.get("pulse_name") or meta.get("link_pulse_name") or "OTX pulse").strip()
            or "OTX pulse"
        )
        adversary = (meta.get("adversary") or meta.get("link_adversary") or "").strip()
        malware = _parse_json_list(meta.get("malware_families") or meta.get("link_malware"))
        tags = _parse_json_list(meta.get("tags") or meta.get("link_tags"))
        countries = _parse_json_list(
            meta.get("targeted_countries") or meta.get("link_countries")
        )

        member_rows = await db.execute_fetchall(
            """
            SELECT DISTINCT ocp.cve_id
            FROM otx_cve_pulses ocp
            INNER JOIN cves c ON c.cve_id = ocp.cve_id
            WHERE ocp.pulse_id = ?
            ORDER BY ocp.cve_id ASC
            """,
            (pulse_id,),
        )
        members = [row["cve_id"] for row in member_rows]
        members = members[: get_max_campaign_members()]
        if len(members) < 2:
            continue

        confidence = _confidence_for_pulse(len(members))
        await db.execute(
            """
            INSERT INTO correlation_campaigns (
                campaign_id, primary_pulse_id, label, adversary, malware_families,
                tags, targeted_countries, confidence, member_count, lifecycle,
                campaign_version, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign_id,
                pulse_id,
                label,
                adversary,
                json.dumps(malware),
                json.dumps(tags),
                json.dumps(countries),
                confidence,
                len(members),
                "active",
                CAMPAIGN_ALGORITHM_VERSION,
                now,
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


async def get_campaigns_for_cve(db, cve_id: str) -> list[dict]:
    """Return campaign clusters containing cve_id with hub filtering applied."""
    cve_upper = cve_id.upper()

    rows = await db.execute_fetchall(
        """
        SELECT c.campaign_id, c.primary_pulse_id, c.label, c.adversary,
               c.malware_families, c.tags, c.targeted_countries, c.confidence,
               c.member_count, c.lifecycle, c.campaign_version, c.computed_at
        FROM correlation_campaigns c
        INNER JOIN correlation_campaign_members m ON m.campaign_id = c.campaign_id
        WHERE m.cve_id = ?
        ORDER BY c.member_count DESC, c.label ASC
        """,
        (cve_upper,),
    )

    results: list[dict] = []
    for row in rows:
        member_rows = await db.execute_fetchall(
            """
            SELECT cve_id FROM correlation_campaign_members
            WHERE campaign_id = ?
            ORDER BY cve_id ASC
            """,
            (row["campaign_id"],),
        )
        all_members = [r["cve_id"] for r in member_rows]
        pulse_counts = await _pulse_counts_for_cves(db, all_members)
        filtered = filter_campaign_members(
            cve_upper, all_members, pulse_counts
        )
        if len(filtered) < 2:
            continue

        evidence = [
            {
                "type": "same_pulse",
                "pulse_id": row["primary_pulse_id"],
                "pulse_name": row["label"],
            }
        ]

        results.append({
            "campaign_id": row["campaign_id"],
            "label": row["label"],
            "primary_pulse_id": row["primary_pulse_id"],
            "adversary": row["adversary"] or "",
            "malware_families": _parse_json_list(row["malware_families"]),
            "tags": _parse_json_list(row["tags"]),
            "targeted_countries": _parse_json_list(row["targeted_countries"]),
            "members": filtered,
            "member_count": len(filtered),
            "confidence": row["confidence"],
            "lifecycle": row["lifecycle"] or "active",
            "evidence": evidence,
            "summary": (
                f"Linked to {len(filtered) - 1} other CVE(s) via OTX pulse "
                f"\"{row['label']}\"."
            ),
            "sources": ["otx"],
            "attribution_disclaimer": "OTX community pulse — unverified attribution",
        })

    return results
