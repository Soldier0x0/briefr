"""Analyst dismiss / suppress feedback for correlation findings."""

from __future__ import annotations

import json
from typing import Any

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
) -> dict:
    from database import insert_correlation_suppression

    if scope not in VALID_SCOPES:
        raise ValueError(f"Invalid scope: {scope}")
    sk = scope_key_for(scope, key)
    if not sk:
        raise ValueError("Missing scope key")
    row = await insert_correlation_suppression(
        db, cve_id.upper(), scope, sk, reason.strip()
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


def is_infrastructure_suppressed(suppressions: list[dict], peer_cve: str) -> bool:
    peer = peer_cve.upper()
    return any(
        s["scope"] == "infrastructure" and s["scope_key"] == peer
        or s["scope"] == "cve_pair" and s["scope_key"] == peer
        for s in suppressions
    )
