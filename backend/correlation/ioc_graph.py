"""Multi-IOC infrastructure edges between CVEs (Correlation v2 Phase 2)."""

from __future__ import annotations

from typing import Any

from correlation.confidence import (
    aggregate_infrastructure_confidence,
    confidence_for_ioc_edge,
)
from correlation.confirm import confirmation_receipt, confirmations_for_iocs_batch
from correlation.copy import infrastructure_summary
from correlation.ioc_normalize import is_noise_ip


async def _shared_ioc_rows(db, cve_id: str) -> list:
    cve_upper = cve_id.upper()
    return await db.execute_fetchall(
        """
        SELECT ocp2.cve_id AS cve_id_b,
               oi.ioc_type,
               oi.ioc_value
        FROM otx_pulse_iocs oi
        JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id AND ocp.cve_id = ?
        JOIN otx_pulse_iocs oi2
            ON oi2.ioc_type = oi.ioc_type AND oi2.ioc_value = oi.ioc_value
        JOIN otx_cve_pulses ocp2 ON ocp2.pulse_id = oi2.pulse_id AND ocp2.cve_id != ?
        JOIN cves c ON c.cve_id = ocp2.cve_id
        GROUP BY ocp2.cve_id, oi.ioc_type, oi.ioc_value
        ORDER BY ocp2.cve_id ASC
        """,
        (cve_upper, cve_upper),
    )


def _count_by_type(edges: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"IP": 0, "DOMAIN": 0, "HASH": 0, "URL": 0}
    for edge in edges:
        t = (edge.get("ioc_type") or "").upper()
        if t in ("IPV4", "IPV6"):
            t = "IP"
        if t in counts:
            counts[t] += 1
    return counts


async def find_shared_infrastructure_v2(
    db, cve_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Peer CVEs linked by shared OTX pulse IOCs (all normalized types)."""
    rows = await _shared_ioc_rows(db, cve_id)
    confirmations_by_value = await confirmations_for_iocs_batch(
        db, [row["ioc_value"] for row in rows]
    )
    by_peer: dict[str, list[dict]] = {}

    for row in rows:
        peer = row["cve_id_b"]
        ioc_type = row["ioc_type"]
        ioc_value = row["ioc_value"]
        confirmations = confirmations_by_value.get(ioc_value, {})
        noise = ioc_type.upper() == "IP" and is_noise_ip(ioc_value)
        conf, why = confidence_for_ioc_edge(
            ioc_type,
            confirmations=confirmations,
            is_noise_ip=noise,
        )
        edge = {
            "ioc_type": ioc_type,
            "ioc_value": ioc_value,
            "confidence": conf,
            "why_not_higher": why,
        }
        receipt = confirmation_receipt(confirmations)
        if receipt:
            edge["confirmation"] = receipt
        by_peer.setdefault(peer, []).append(edge)

    results: list[dict[str, Any]] = []
    for peer, edges in sorted(by_peer.items())[:limit]:
        counts = _count_by_type(edges)
        confidence, evidence, why = aggregate_infrastructure_confidence(edges)

        results.append({
            "cve_id_b": peer,
            "shared_ip_count": counts["IP"],
            "shared_domain_count": counts["DOMAIN"],
            "shared_hash_count": counts["HASH"],
            "shared_url_count": counts["URL"],
            "shared_ioc_count": sum(counts.values()),
            "confidence": confidence,
            "evidence": evidence,
            "summary": infrastructure_summary(peer, counts),
            "sources": ["otx"],
            "why_not_higher": why,
        })

    results.sort(
        key=lambda x: (
            -x["shared_hash_count"],
            -x["shared_domain_count"],
            -x["shared_url_count"],
            -x["shared_ip_count"],
        )
    )
    return results


async def ioc_edges_between(
    db, cve_id_a: str, cve_id_b: str
) -> list[dict[str, Any]]:
    """Shared IOC edges for a specific CVE pair (campaign enrichment)."""
    rows = await db.execute_fetchall(
        """
        SELECT oi.ioc_type, oi.ioc_value
        FROM otx_pulse_iocs oi
        JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id AND ocp.cve_id = ?
        JOIN otx_pulse_iocs oi2
            ON oi2.ioc_type = oi.ioc_type AND oi2.ioc_value = oi.ioc_value
        JOIN otx_cve_pulses ocp2 ON ocp2.pulse_id = oi2.pulse_id AND ocp2.cve_id = ?
        GROUP BY oi.ioc_type, oi.ioc_value
        """,
        (cve_id_a.upper(), cve_id_b.upper()),
    )
    edges = []
    for row in rows:
        edges.append({
            "ioc_type": row["ioc_type"],
            "ioc_value": row["ioc_value"],
        })
    return edges


async def related_cves_for_ioc(
    db, ioc_type: str, ioc_value: str, limit: int = 50
) -> list[str]:
    """CVE IDs sharing a canonical IOC (unified with correlation tables)."""
    from correlation.ioc_normalize import normalize_ioc

    normalized = normalize_ioc(ioc_type, ioc_value)
    if normalized is None:
        return []
    canon_type, canon_value, _meta = normalized

    rows = await db.execute_fetchall(
        """
        SELECT ocp.cve_id
        FROM otx_pulse_iocs oi
        JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id
        JOIN cves c ON c.cve_id = ocp.cve_id
        WHERE oi.ioc_type = ? AND oi.ioc_value = ?
        GROUP BY ocp.cve_id
        ORDER BY ocp.cve_id ASC
        LIMIT ?
        """,
        (canon_type, canon_value, limit),
    )
    return [row["cve_id"] for row in rows]


async def batch_ioc_edges_for_peers(
    db, cve_id_a: str, peers: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Shared IOC edges for cve_id_a and a list of peer CVEs (batch optimized)."""
    if not peers:
        return {}
    cve_upper = cve_id_a.upper()
    peers_upper = [p.upper() for p in peers]
    pg = type(db).__name__ == "PostgresConnection"
    placeholders = ",".join(f"${i+2}" if pg else "?" for i in range(len(peers_upper)))
    bind_args = [cve_upper] + peers_upper
    
    rows = await db.execute_fetchall(
        f"""
        SELECT ocp2.cve_id AS peer_cve, oi.ioc_type, oi.ioc_value
        FROM otx_pulse_iocs oi
        JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id AND ocp.cve_id = $1
        JOIN otx_pulse_iocs oi2
            ON oi2.ioc_type = oi.ioc_type AND oi2.ioc_value = oi.ioc_value
        JOIN otx_cve_pulses ocp2 ON ocp2.pulse_id = oi2.pulse_id AND ocp2.cve_id IN ({placeholders})
        GROUP BY ocp2.cve_id, oi.ioc_type, oi.ioc_value
        """ if pg else f"""
        SELECT ocp2.cve_id AS peer_cve, oi.ioc_type, oi.ioc_value
        FROM otx_pulse_iocs oi
        JOIN otx_cve_pulses ocp ON ocp.pulse_id = oi.pulse_id AND ocp.cve_id = ?
        JOIN otx_pulse_iocs oi2
            ON oi2.ioc_type = oi.ioc_type AND oi2.ioc_value = oi.ioc_value
        JOIN otx_cve_pulses ocp2 ON ocp2.pulse_id = oi2.pulse_id AND ocp2.cve_id IN ({placeholders})
        GROUP BY ocp2.cve_id, oi.ioc_type, oi.ioc_value
        """,
        tuple(bind_args),
    )
    
    by_peer: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        peer = row["peer_cve"]
        by_peer.setdefault(peer, []).append({
            "ioc_type": row["ioc_type"],
            "ioc_value": row["ioc_value"],
        })
    return by_peer

