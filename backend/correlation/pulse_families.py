"""Pulse family clustering for campaign dedup (CORR-PR-9)."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from correlation.config import get_hub_cve_pulse_cap
from correlation.lifecycle import _parse_dt

_JACCARD_THRESHOLD = 0.7
_MIN_IOCS_FOR_JACCARD = 3


def normalize_pulse_name(name: str) -> str:
    text = re.sub(r"\s+", " ", (name or "").strip().lower())
    return text


def family_id_for_oldest_pulse(oldest_pulse_id: str) -> str:
    digest = hashlib.sha256(oldest_pulse_id.encode()).hexdigest()[:12]
    return f"fam_{digest}"


def campaign_id_for_family(family_id: str, oldest_pulse_id: str) -> str:
    """Stable campaign id anchored on the family's oldest pulse (spec §10)."""
    _ = family_id
    digest = hashlib.sha256(oldest_pulse_id.encode()).hexdigest()[:12]
    return f"camp_{digest}"


def legacy_campaign_id_for_pulse(pulse_id: str) -> str:
    """Pre-PR-9 per-pulse campaign id (for suppression migration)."""
    digest = hashlib.sha256(pulse_id.encode()).hexdigest()[:12]
    return f"camp_{digest}"


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _union_find_parent(parent: dict[str, str], node: str) -> str:
    parent.setdefault(node, node)
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _union_find_merge(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _union_find_parent(parent, a), _union_find_parent(parent, b)
    if ra != rb:
        parent[rb] = ra


def _oldest_pulse_id(pulse_ids: list[str], created_map: dict[str, str]) -> str:
    def sort_key(pid: str) -> tuple:
        dt = _parse_dt(created_map.get(pid))
        if dt is None:
            return (1, pid)
        return (0, dt.timestamp(), pid)

    return sorted(pulse_ids, key=sort_key)[0]


async def rebuild_pulse_families(db) -> dict[str, Any]:
    """
    Assign each OTX pulse to a family (connected components).
    Rules (spec §10): Jaccard ≥ 0.7 on non-hub IOC sets (≥3 IOCs each), OR
    identical CVE member sets with identical normalized pulse names.
    """
    from db.timeutil import utcnow_str

    hub_cap = get_hub_cve_pulse_cap()
    pulse_rows = await db.execute_fetchall(
        """
        SELECT p.pulse_id, p.pulse_name, p.author, p.created_date,
               COUNT(DISTINCT ocp.cve_id) AS cve_count
        FROM otx_pulses p
        INNER JOIN otx_cve_pulses ocp ON ocp.pulse_id = p.pulse_id
        INNER JOIN cves c ON c.cve_id = ocp.cve_id
        GROUP BY p.pulse_id, p.pulse_name, p.author, p.created_date
        HAVING COUNT(DISTINCT ocp.cve_id) >= 2
        """
    )
    if not pulse_rows:
        await db.execute("DELETE FROM pulse_families")
        return {"families": 0, "pulses": 0}

    pulse_ids = [row["pulse_id"] for row in pulse_rows]
    created_map = {row["pulse_id"]: row["created_date"] or "" for row in pulse_rows}
    name_map = {row["pulse_id"]: normalize_pulse_name(row["pulse_name"] or "") for row in pulse_rows}

    cve_rows = await db.execute_fetchall(
        f"""
        SELECT pulse_id, cve_id
        FROM otx_cve_pulses
        WHERE pulse_id IN ({",".join("?" * len(pulse_ids))})
        """,
        tuple(pulse_ids),
    )
    cve_sets: dict[str, set[str]] = defaultdict(set)
    for row in cve_rows:
        cve_sets[row["pulse_id"]].add(row["cve_id"])

    ioc_rows = await db.execute_fetchall(
        f"""
        SELECT oi.pulse_id, oi.ioc_type, oi.ioc_value,
               COALESCE(deg.cve_count, 0) AS degree
        FROM otx_pulse_iocs oi
        LEFT JOIN ioc_degree deg
            ON deg.ioc_type = oi.ioc_type AND deg.ioc_value = oi.ioc_value
        WHERE oi.pulse_id IN ({",".join("?" * len(pulse_ids))})
        """,
        tuple(pulse_ids),
    )
    ioc_sets: dict[str, set[str]] = defaultdict(set)
    for row in ioc_rows:
        if int(row["degree"] or 0) > hub_cap:
            continue
        key = f"{row['ioc_type']}:{row['ioc_value']}"
        ioc_sets[row["pulse_id"]].add(key)

    parent: dict[str, str] = {pid: pid for pid in pulse_ids}

    # Identical CVE + name pairs
    buckets: dict[tuple[frozenset[str], str], list[str]] = defaultdict(list)
    for pid in pulse_ids:
        buckets[(frozenset(cve_sets.get(pid, set())), name_map.get(pid, ""))].append(pid)
    for group in buckets.values():
        if len(group) < 2:
            continue
        anchor = group[0]
        for other in group[1:]:
            _union_find_merge(parent, anchor, other)

    # Shared IOC candidate pairs with Jaccard ≥ threshold
    ioc_to_pulses: dict[str, list[str]] = defaultdict(list)
    for pid, iocs in ioc_sets.items():
        if len(iocs) < _MIN_IOCS_FOR_JACCARD:
            continue
        for ioc in iocs:
            ioc_to_pulses[ioc].append(pid)

    seen_pairs: set[tuple[str, str]] = set()
    for pulses in ioc_to_pulses.values():
        if len(pulses) < 2:
            continue
        for i in range(len(pulses)):
            for j in range(i + 1, len(pulses)):
                a, b = pulses[i], pulses[j]
                pair = tuple(sorted((a, b)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                set_a, set_b = ioc_sets[a], ioc_sets[b]
                if len(set_a) < _MIN_IOCS_FOR_JACCARD or len(set_b) < _MIN_IOCS_FOR_JACCARD:
                    continue
                if _jaccard(set_a, set_b) >= _JACCARD_THRESHOLD:
                    _union_find_merge(parent, a, b)

    families: dict[str, list[str]] = defaultdict(list)
    for pid in pulse_ids:
        root = _union_find_parent(parent, pid)
        families[root].append(pid)

    now = utcnow_str()
    await db.execute("DELETE FROM pulse_families")
    family_count = 0
    for _root, members in families.items():
        oldest = _oldest_pulse_id(members, created_map)
        fam_id = family_id_for_oldest_pulse(oldest)
        family_count += 1
        for pid in members:
            await db.execute(
                """
                INSERT INTO pulse_families (pulse_id, family_id, jaccard, computed_at)
                VALUES (?, ?, ?, ?)
                """,
                (pid, fam_id, None, now),
            )

    return {"families": family_count, "pulses": len(pulse_ids)}


async def family_map_for_pulses(db, pulse_ids: list[str]) -> dict[str, str]:
    if not pulse_ids:
        return {}
    placeholders = ",".join("?" * len(pulse_ids))
    rows = await db.execute_fetchall(
        f"""
        SELECT pulse_id, family_id FROM pulse_families
        WHERE pulse_id IN ({placeholders})
        """,
        tuple(pulse_ids),
    )
    return {row["pulse_id"]: row["family_id"] for row in rows}


async def legacy_campaign_ids_for_family(db, family_id: str) -> list[str]:
    rows = await db.execute_fetchall(
        "SELECT pulse_id FROM pulse_families WHERE family_id = ?",
        (family_id,),
    )
    return [legacy_campaign_id_for_pulse(row["pulse_id"]) for row in rows]
