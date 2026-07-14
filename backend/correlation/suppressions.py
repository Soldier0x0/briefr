"""Analyst dismiss / suppress feedback for correlation findings."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from correlation.lifecycle import _parse_dt
from correlation.pulse_families import campaign_id_for_family, legacy_campaign_id_for_pulse

VALID_SCOPES = frozenset({"campaign_id", "cve_pair", "pulse_id", "infrastructure"})


def scope_key_for(scope: str, key: dict[str, Any]) -> str:
    if scope == "campaign_id":
        return str(key.get("campaign_id") or "")
    if scope == "cve_pair":
        return str(key.get("cve_id_b") or key.get("peer_cve") or "").upper()
    if scope == "pulse_id":
        return str(key.get("pulse_id") or "")
    if scope == "infrastructure":
        return str(key.get("cve_id_b") or "").upper()
    return json.dumps(key, sort_keys=True)


async def add_suppression(
    db,
    cve_id: str,
    scope: str,
    key: dict[str, Any],
    reason: str = "",
    dismissed_by: str = "",
) -> dict:
    from database import insert_correlation_suppression

    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope}")
    sk = scope_key_for(scope, key)
    if not sk:
        raise ValueError("Missing scope key")
    row = await insert_correlation_suppression(
        db, cve_id.upper(), scope, sk, reason.strip(), dismissed_by.strip()
    )
    return row


async def remove_suppression(
    db, cve_id: str, scope: str, key: dict[str, Any]
) -> bool:
    from database import delete_correlation_suppression

    sk = scope_key_for(scope, key)
    return await delete_correlation_suppression(db, cve_id.upper(), scope, sk)


async def load_suppressions(db, cve_id: str) -> list[dict]:
    from database import list_correlation_suppressions

    return await list_correlation_suppressions(db, cve_id.upper())


def is_campaign_suppressed(suppressions: list[dict], campaign_id: str) -> bool:
    return any(
        s["scope"] == "campaign_id" and s["scope_key"] == campaign_id
        for s in suppressions
    )


async def resolve_suppressed_campaign_ids(db, suppressions: list[dict]) -> set[str]:
    """
    Campaign ids treated as suppressed, including legacy per-pulse ids mapped
    to their pulse-family campaign (CORR-PR-9).
    """
    direct = {
        s["scope_key"]
        for s in suppressions
        if s["scope"] == "campaign_id" and s["scope_key"]
    }
    if not direct:
        return set()

    rows = await db.execute_fetchall(
        """
        SELECT pf.pulse_id, pf.family_id, p.created_date
        FROM pulse_families pf
        LEFT JOIN otx_pulses p ON p.pulse_id = pf.pulse_id
        """
    )
    if not rows:
        return direct

    families: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(dict(row))

    expanded = set(direct)
    for fam_id, members in families.items():
        legacy_ids = {legacy_campaign_id_for_pulse(m["pulse_id"]) for m in members}
        if not (legacy_ids & direct):
            continue
        oldest = sorted(
            members,
            key=lambda m: (
                _parse_dt(m.get("created_date"))
                or datetime(1970, 1, 1, tzinfo=timezone.utc),
                m["pulse_id"],
            ),
        )[0]
        expanded.add(campaign_id_for_family(fam_id, oldest["pulse_id"]))
    return expanded


def is_infrastructure_suppressed(suppressions: list[dict], peer_cve: str) -> bool:
    peer = peer_cve.upper()
    return any(
        s["scope"] == "infrastructure" and s["scope_key"] == peer
        or s["scope"] == "cve_pair" and s["scope_key"] == peer
        for s in suppressions
    )
