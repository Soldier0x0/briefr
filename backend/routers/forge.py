"""Forge MVP (Beta V1.3 Theme 3) — detection engineering inside the intel pane.

Endpoints:
- GET  /api/forge/coverage          — MITRE coverage map: stack profile ×
  techniques × rule status (community / yours / gap)
- GET  /api/hunt-packs/{technique_id} — hunt pack content for one technique
  (saved packs, template baseline, linked CVEs)
- POST /api/hunt-packs/generate     — generate + persist a CVE→pack link

Everything is local and deterministic: built on the existing template library
(detection.sigma_generator / detection.siem_queries) and the cve_technique_map
populated by the MITRE feed. No outbound HTTP — community-rule *search*
(SigmaHQ/Elastic via GitHub) stays on GET /api/cves/{cve_id}/detection.

Coverage status semantics (MVP):
- "yours":     at least one saved hunt pack exists for the technique
- "community": the curated template library covers the technique
               (community-aligned Sigma/SIEM content ships with BRIEFR)
- "gap":       neither — a real detection-engineering gap

Out of scope (per Beta V1.3.md): rule proof on live logs (V1.5),
HyperDX provisioning (V1.4/V1.5).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_db
from detection.sigma_generator import TECHNIQUE_TEMPLATES, generate_sigma_rule
from detection.context import get_detection_context
from detection.siem_queries import TECHNIQUE_QUERIES, get_siem_queries
from routers.cves import _stack_match_clause

router = APIRouter()

# Techniques the bundled template library covers (sub-techniques inherit the
# parent's coverage — T1059.001 falls under T1059).
_COMMUNITY_TECHNIQUES: frozenset[str] = frozenset(
    set(TECHNIQUE_TEMPLATES) | (set(TECHNIQUE_QUERIES) - {"DEFAULT"})
)

_TECHNIQUE_ID_RE = re.compile(r"T\d{4}(\.\d{3})?", re.IGNORECASE)


def _validate_technique_id(value: str) -> str:
    tid = (value or "").strip().upper()
    if not _TECHNIQUE_ID_RE.fullmatch(tid):
        raise HTTPException(status_code=400, detail="Invalid ATT&CK technique ID")
    return tid


def _technique_prefix(technique_id: str) -> str:
    """Parent technique ID — T1059.001 → T1059."""
    return technique_id.split(".")[0]


def _coverage_status(pack_count: int, technique_id: str) -> str:
    if pack_count > 0:
        return "yours"
    if _technique_prefix(technique_id) in _COMMUNITY_TECHNIQUES:
        return "community"
    return "gap"


def _loads_or(value, fallback):
    if not value:
        return fallback
    # Pass through already-deserialized values (mock data, auto-deserializing
    # drivers) — json.loads would raise TypeError and mask them as fallback.
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _pack_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "technique_id": row["technique_id"],
        "cve_id": row["cve_id"],
        "title": row["title"],
        "priority": row["priority"],
        "sigma_yaml": row["sigma_yaml"],
        "siem_queries": _loads_or(row["siem_queries"], {}),
        "log_patterns": _loads_or(row["log_patterns"], []),
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── Coverage map ──────────────────────────────────────────

@router.get("/api/forge/coverage")
async def forge_coverage(
    stack: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated stack terms (same matching as /api/cves)",
    ),
):
    """
    MITRE coverage map: techniques linked to CVEs in the database (optionally
    filtered to the analyst's stack), each with CVE/KEV exposure counts and a
    rule status of "yours" (saved hunt pack), "community" (bundled template
    library covers it), or "gap" (no detection content at all).
    """
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)

    # Stack filter runs as a subselect on cves alone — the clause references
    # unqualified cves columns and must not collide with the join below.
    cve_filter = ""
    params: list = []
    if stack_clause:
        cve_filter = f"WHERE m.cve_id IN (SELECT cve_id FROM cves WHERE {stack_clause})"
        params = list(stack_params)

    db = await get_db()
    try:
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
            """,
            params,
        )
        pack_rows = await db.execute_fetchall(
            "SELECT technique_id, COUNT(*) AS pack_count FROM hunt_packs GROUP BY technique_id"
        )
        technique_rows = await db.execute_fetchall(
            "SELECT technique_id, name, tactic, url FROM mitre_techniques"
        )
    finally:
        await db.close()

    packs_by_technique = {r["technique_id"]: r["pack_count"] for r in pack_rows}
    meta_by_technique = {
        r["technique_id"]: {"name": r["name"], "tactic": r["tactic"], "url": r["url"]}
        for r in technique_rows
    }

    techniques: list[dict] = []
    status_counts = {"yours": 0, "community": 0, "gap": 0}
    seen: set[str] = set()
    for row in exposure_rows:
        tid = row["technique_id"]
        seen.add(tid)
        pack_count = packs_by_technique.get(tid, 0)
        status = _coverage_status(pack_count, tid)
        status_counts[status] += 1
        meta = meta_by_technique.get(tid, {})
        techniques.append({
            "technique_id": tid,
            "name": meta.get("name", ""),
            "tactic": meta.get("tactic", ""),
            "url": meta.get("url", ""),
            "cve_count": row["cve_count"] or 0,
            "kev_count": row["kev_count"] or 0,
            "max_epss": row["max_epss"],
            "pack_count": pack_count,
            "status": status,
        })

    # Techniques with saved packs always stay on the map, even when the
    # current stack filter matches none of their CVEs.
    for tid, pack_count in packs_by_technique.items():
        if tid in seen:
            continue
        status = _coverage_status(pack_count, tid)
        status_counts[status] += 1
        meta = meta_by_technique.get(tid, {})
        techniques.append({
            "technique_id": tid,
            "name": meta.get("name", ""),
            "tactic": meta.get("tactic", ""),
            "url": meta.get("url", ""),
            "cve_count": 0,
            "kev_count": 0,
            "max_epss": None,
            "pack_count": pack_count,
            "status": status,
        })

    # Gaps (then community) first within each tactic — the map is a worklist.
    status_rank = {"gap": 0, "community": 1, "yours": 2}
    techniques.sort(
        key=lambda t: (
            t["tactic"] or "~",
            status_rank.get(t["status"], 3),
            -(t["kev_count"] or 0),
            -(t["cve_count"] or 0),
            t["technique_id"],
        )
    )

    return {
        "techniques": techniques,
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stack_terms": stack_terms,
            "counts": status_counts,
            "technique_total": len(techniques),
        },
    }


# ── Hunt pack generation (CVE → pack linkage) ─────────────

class HuntPackGenerateRequest(BaseModel):
    cve_id: str = Field(min_length=1, max_length=30)
    technique_id: str | None = Field(default=None, max_length=12)


def _derive_priority(is_kev, cvss_score, epss_score) -> str:
    if is_kev:
        return "critical"
    cvss = cvss_score or 0.0
    epss = epss_score or 0.0
    if cvss >= 9.0 or epss >= 0.5:
        return "high"
    if cvss >= 7.0 or epss >= 0.1:
        return "medium"
    return "low"


def _first_product(affected_products_json) -> str:
    products = _loads_or(affected_products_json, [])
    if not products or not isinstance(products, list):
        return ""
    first = str(products[0])
    # Stored as "vendor:product" — the product half makes the better title.
    return first.split(":")[-1].replace("_", " ").strip()


@router.post("/api/hunt-packs/generate")
async def generate_hunt_pack(payload: HuntPackGenerateRequest):
    """
    Generate a detection pack for a CVE and persist the CVE→pack link.
    Idempotent: regenerating for the same (technique, CVE) pair updates the
    existing row in place. Content comes from the bundled template library —
    no outbound calls, no API quota.
    """
    cve_id = payload.cve_id.strip().upper()
    if not cve_id.startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, description, affected_products, mitre_technique,
                   is_kev, cvss_score, epss_score, cwe_ids
            FROM cves WHERE cve_id = ?
            """,
            (cve_id,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail="CVE not found")
        cve = rows[0]

        if payload.technique_id:
            technique_id = _validate_technique_id(payload.technique_id)
        else:
            technique_id = (cve["mitre_technique"] or "").strip().upper()
            if not technique_id:
                mapped = await db.execute_fetchall(
                    "SELECT technique_id FROM cve_technique_map WHERE cve_id = ? "
                    "ORDER BY technique_id LIMIT 1",
                    (cve_id,),
                )
                technique_id = mapped[0]["technique_id"] if mapped else ""
            if not technique_id:
                raise HTTPException(
                    status_code=400,
                    detail="No ATT&CK technique linked to this CVE — pass technique_id",
                )

        name_rows = await db.execute_fetchall(
            "SELECT name FROM mitre_techniques WHERE technique_id = ?",
            (technique_id,),
        )
        technique_name = name_rows[0]["name"] if name_rows else technique_id

        product = _first_product(cve["affected_products"])
        description = (cve["description"] or "")[:200]
        priority = _derive_priority(cve["is_kev"], cve["cvss_score"], cve["epss_score"])
        cwe_ids: list[str] = []
        raw_cwe = cve["cwe_ids"]
        if raw_cwe:
            try:
                parsed = json.loads(raw_cwe) if isinstance(raw_cwe, str) else raw_cwe
                if isinstance(parsed, list):
                    cwe_ids = [str(c) for c in parsed if str(c).strip()]
            except (json.JSONDecodeError, TypeError):
                cwe_ids = []

        detection_context = await get_detection_context(db, cve_id)
        sigma_yaml = generate_sigma_rule(
            cve_id=cve_id,
            technique_id=technique_id,
            product=product or "Affected Product",
            description=description,
            cwe_ids=cwe_ids,
            detection_context=detection_context,
        )
        siem = get_siem_queries(
            technique_id=technique_id,
            cve_id=cve_id,
            product=product,
            cwe_ids=cwe_ids,
            detection_context=detection_context,
        )
        log_patterns = siem.pop("log_patterns", [])
        title = f"{cve_id} — {technique_name} hunt pack"

        existing = await db.execute_fetchall(
            "SELECT id FROM hunt_packs WHERE technique_id = ? AND cve_id = ?",
            (technique_id, cve_id),
        )
        created = not existing

        from db.dialect import utcnow_str
        await db.execute(
            """
            INSERT INTO hunt_packs
                (technique_id, cve_id, title, priority, sigma_yaml,
                 siem_queries, log_patterns)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(technique_id, cve_id) DO UPDATE SET
                title = excluded.title,
                priority = excluded.priority,
                sigma_yaml = excluded.sigma_yaml,
                siem_queries = excluded.siem_queries,
                log_patterns = excluded.log_patterns,
                updated_at = ?
            """,
            (
                technique_id,
                cve_id,
                title,
                priority,
                sigma_yaml,
                json.dumps(siem),
                json.dumps(log_patterns),
                utcnow_str(),
            ),
        )
        await db.commit()

        pack_rows = await db.execute_fetchall(
            "SELECT * FROM hunt_packs WHERE technique_id = ? AND cve_id = ?",
            (technique_id, cve_id),
        )
    finally:
        await db.close()

    return {"pack": _pack_to_dict(pack_rows[0]), "created": created}


# ── Hunt pack API (registered after the literal /generate sibling) ──

@router.get("/api/hunt-packs/{technique_id}")
async def get_hunt_pack(technique_id: str):
    """
    Hunt pack content for one ATT&CK technique: technique metadata, saved
    packs (CVE-linked), the template baseline (SIEM queries + log patterns),
    and the CVEs mapped to the technique for "Generate pack" pivots.
    """
    tid = _validate_technique_id(technique_id)

    db = await get_db()
    try:
        technique_rows = await db.execute_fetchall(
            "SELECT technique_id, name, description, tactic, url, platforms, detection "
            "FROM mitre_techniques WHERE technique_id = ?",
            (tid,),
        )
        pack_rows = await db.execute_fetchall(
            "SELECT * FROM hunt_packs WHERE technique_id = ? ORDER BY updated_at DESC",
            (tid,),
        )
        cve_rows = await db.execute_fetchall(
            """
            SELECT c.cve_id, c.severity, c.cvss_score, c.epss_score,
                   c.is_kev, c.published
            FROM cve_technique_map m
            JOIN cves c ON c.cve_id = m.cve_id
            WHERE m.technique_id = ?
            ORDER BY c.is_kev DESC,
                     CASE WHEN c.epss_score IS NOT NULL THEN c.epss_score ELSE -1 END DESC,
                     c.published DESC
            LIMIT 20
            """,
            (tid,),
        )
    finally:
        await db.close()

    if not technique_rows and not pack_rows and not cve_rows:
        raise HTTPException(status_code=404, detail="Technique not found")

    technique: dict = {"technique_id": tid, "name": tid, "description": "",
                       "tactic": "", "url": "", "platforms": [], "detection": ""}
    if technique_rows:
        row = technique_rows[0]
        technique = {
            "technique_id": row["technique_id"],
            "name": row["name"],
            "description": row["description"] or "",
            "tactic": row["tactic"] or "",
            "url": row["url"],
            "platforms": _loads_or(row["platforms"], []),
            "detection": row["detection"] or "",
        }

    baseline = get_siem_queries(technique_id=tid)
    log_patterns = baseline.pop("log_patterns", [])

    return {
        "technique": technique,
        "status": _coverage_status(len(pack_rows), tid),
        "packs": [_pack_to_dict(r) for r in pack_rows],
        "siem_queries": baseline,
        "log_patterns": log_patterns,
        "linked_cves": [
            {
                "cve_id": r["cve_id"],
                "severity": r["severity"],
                "cvss_score": r["cvss_score"],
                "epss_score": r["epss_score"],
                "is_kev": bool(r["is_kev"]),
                "published": r["published"],
            }
            for r in cve_rows
        ],
    }
