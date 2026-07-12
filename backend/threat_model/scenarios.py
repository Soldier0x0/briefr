"""Environment threat scenarios (V1.5 Theme 1).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from routers.cves import _stack_match_clause
from routers.forge import _COMMUNITY_TECHNIQUES, _coverage_status, _technique_prefix


def _scenario_summary(
    *,
    name: str,
    tactic: str,
    cve_count: int,
    kev_count: int,
    stack_terms: list[str],
    detection_hint: str,
    status: str,
) -> str:
    stack_label = ", ".join(stack_terms[:4]) if stack_terms else "your stack"
    if kev_count:
        exposure = f"{kev_count} KEV and {cve_count} total CVE(s)"
    elif cve_count:
        exposure = f"{cve_count} open CVE(s)"
    else:
        exposure = "mapped CVE exposure"

    opener = (
        f"An adversary may use {name} ({tactic or 'ATT&CK'}) against systems running {stack_label}. "
        f"BRIEFR links {exposure} on your stack to this technique."
    )
    if status == "gap":
        opener += " No bundled or saved detection content covers this technique yet — treat as a coverage gap."
    elif status == "community":
        opener += " Community hunt templates exist — validate and tune before production."
    else:
        opener += " You have saved hunt packs for this technique."

    hint = (detection_hint or "").strip()
    if hint:
        snippet = hint.split(".")[0].strip()
        if snippet and len(snippet) > 20:
            opener += f" Detection focus: {snippet}."
    return opener


def _mitigation_actions(
    *,
    technique_id: str,
    status: str,
    linked_cves: list[dict[str, Any]],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for cve in linked_cves[:3]:
        cve_id = cve["cve_id"]
        if cve.get("is_kev"):
            actions.append(
                {
                    "type": "patch",
                    "label": f"Patch or mitigate {cve_id} (CISA KEV)",
                    "cve_id": cve_id,
                    "technique_id": technique_id,
                }
            )
        actions.append(
            {
                "type": "hunt_pack",
                "label": f"Generate hunt pack for {cve_id}",
                "cve_id": cve_id,
                "technique_id": technique_id,
            }
        )
    if status == "gap":
        actions.append(
            {
                "type": "detect",
                "label": "Close detection gap in Forge",
                "technique_id": technique_id,
            }
        )
    elif status == "community":
        actions.append(
            {
                "type": "validate",
                "label": "Review community SIEM templates in Forge",
                "technique_id": technique_id,
            }
        )
    if not actions:
        actions.append(
            {
                "type": "monitor",
                "label": "Monitor feed for new CVE mappings",
                "technique_id": technique_id,
            }
        )
    return actions


async def build_threat_scenarios(db: Any, stack: str | None) -> dict[str, Any]:
    """Stack-scoped ATT&CK scenario cards with CVE evidence and mitigation hints."""
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)

    cve_filter = ""
    params: list = []
    if stack_clause:
        cve_filter = f"WHERE m.cve_id IN (SELECT c.cve_id FROM cves c WHERE {stack_clause})"
        params = list(stack_params)

    exposure_rows = await db.execute_fetchall(
        f"""
        SELECT m.technique_id,
               COUNT(DISTINCT m.cve_id) AS cve_count,
               SUM(CASE WHEN c.is_kev = 1 THEN 1 ELSE 0 END) AS kev_count,
               MAX(c.epss_score) AS max_epss
        FROM cve_technique_map m
        JOIN cves c ON c.cve_id = m.cve_id
        {cve_filter}
        GROUP BY m.technique_id
        ORDER BY kev_count DESC,
                 CASE WHEN MAX(c.epss_score) IS NULL THEN 1 ELSE 0 END,
                 max_epss DESC,
                 cve_count DESC
        LIMIT 40
        """,
        params,
    )

    if not exposure_rows:
        return {
            "scenarios": [],
            "meta": {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stack_terms": stack_terms,
                "profile_required": not stack_terms,
                "technique_total": 0,
                "gap_count": 0,
            },
        }

    technique_ids = [r["technique_id"] for r in exposure_rows]
    placeholders = ", ".join("?" for _ in technique_ids)
    technique_rows = await db.execute_fetchall(
        f"""
        SELECT technique_id, name, description, tactic, url, detection
        FROM mitre_techniques
        WHERE technique_id IN ({placeholders})
        """,
        technique_ids,
    )
    meta_by_id = {r["technique_id"]: dict(r) for r in technique_rows}

    pack_rows = await db.execute_fetchall(
        f"""
        SELECT technique_id, COUNT(*) AS pack_count
        FROM hunt_packs
        WHERE technique_id IN ({placeholders})
        GROUP BY technique_id
        """,
        technique_ids,
    )
    packs_by_id = {r["technique_id"]: int(r["pack_count"]) for r in pack_rows}

    scenarios: list[dict[str, Any]] = []
    gap_count = 0

    for row in exposure_rows:
        tid = row["technique_id"]
        pack_count = packs_by_id.get(tid, 0)
        status = _coverage_status(pack_count, tid)
        if status == "gap":
            gap_count += 1

        meta = meta_by_id.get(tid, {})
        cve_rows = await db.execute_fetchall(
            f"""
            SELECT c.cve_id, c.severity, c.cvss_score, c.epss_score, c.is_kev, c.published
            FROM cve_technique_map m
            JOIN cves c ON c.cve_id = m.cve_id
            WHERE m.technique_id = ?
            {"AND c.cve_id IN (SELECT c2.cve_id FROM cves c2 WHERE " + stack_clause.replace("c.", "c2.") + ")" if stack_clause else ""}
            ORDER BY c.is_kev DESC,
                     CASE WHEN c.epss_score IS NOT NULL THEN c.epss_score ELSE -1 END DESC,
                     c.published DESC
            LIMIT 5
            """,
            [tid, *stack_params] if stack_clause else [tid],
        )
        linked = [
            {
                "cve_id": r["cve_id"],
                "severity": r["severity"],
                "cvss_score": r["cvss_score"],
                "epss_score": r["epss_score"],
                "is_kev": bool(r["is_kev"]),
                "published": r["published"],
            }
            for r in cve_rows
        ]

        scenarios.append(
            {
                "technique_id": tid,
                "name": meta.get("name") or tid,
                "tactic": meta.get("tactic") or "",
                "url": meta.get("url") or "",
                "coverage_status": status,
                "community_template": _technique_prefix(tid) in _COMMUNITY_TECHNIQUES,
                "cve_count": int(row["cve_count"] or 0),
                "kev_count": int(row["kev_count"] or 0),
                "scenario": _scenario_summary(
                    name=meta.get("name") or tid,
                    tactic=meta.get("tactic") or "",
                    cve_count=int(row["cve_count"] or 0),
                    kev_count=int(row["kev_count"] or 0),
                    stack_terms=stack_terms,
                    detection_hint=meta.get("detection") or "",
                    status=status,
                ),
                "evidence_cves": linked,
                "mitigations": _mitigation_actions(
                    technique_id=tid,
                    status=status,
                    linked_cves=linked,
                ),
            }
        )

    return {
        "scenarios": scenarios,
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stack_terms": stack_terms,
            "profile_required": not stack_terms,
            "technique_total": len(scenarios),
            "gap_count": gap_count,
        },
    }
