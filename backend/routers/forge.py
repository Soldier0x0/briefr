"""Forge MVP (Beta V1.3 Theme 3) — detection engineering inside the intel pane.

Endpoints:
- GET  /api/forge/coverage          — MITRE coverage map: stack profile ×
  techniques × rule status (community / yours / gap)
- GET  /api/hunt-packs/{technique_id} — hunt pack content for one technique
  (saved packs, template baseline, linked CVEs)
- POST /api/hunt-packs/generate     — generate + persist a CVE→pack link

Everything is local and deterministic: hunt-pack generate uses the detection
composer (`compose_detection_evidence` + `emit_composed_detection`) with
``include_community=False`` so live SigmaHQ/Elastic GitHub search stays off
this path. When the local SigmaHQ Postgres index has a CVE-exact rule, that
YAML is attached as ``sigma_yaml``; otherwise the class/template emit is used.
Evidence still comes from DB/cache (detection_context artifacts, Nuclei URLs,
YARA, SigmaHQ index).

Coverage status semantics (MVP):
- "yours":     at least one saved hunt pack exists for the technique
- "community": the curated template library covers the technique
               (community-aligned Sigma/SIEM content ships with BRIEFR)
- "gap":       neither — a real detection-engineering gap

Out of scope (per Beta V1.3.md): rule proof on live logs (V1.5),
HyperDX provisioning (V1.4/V1.5).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from database import (
    get_case_studies_for_technique,
    get_case_study_counts_by_technique,
    get_db,
)
from detection.composer import compose_detection_evidence, emit_composed_detection
from detection.sigma_generator import TECHNIQUE_TEMPLATES
from detection.sigmahq_index import find_index_rules_for_cve
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

async def build_coverage_map(db, stack: str | None) -> dict:
    """
    MITRE coverage map: techniques linked to CVEs in the database (optionally
    filtered to a stack), each with CVE/KEV exposure counts and a rule status
    of "yours" (saved hunt pack), "community" (bundled template library
    covers it), or "gap" (no detection content at all).

    Extracted from the `/api/forge/coverage` handler so the Security
    Architecture MITRE ATT&CK section (TM-3) can reuse the exact same query
    and status logic instead of duplicating it -- same convention as
    `threat_model.scenarios.build_threat_scenarios` being wrapped, not
    reimplemented. Caller owns the `db` connection lifecycle.
    """
    stack_clause, stack_params, stack_terms = _stack_match_clause(stack)

    # Stack filter runs as a subselect on cves alone — the clause references
    # unqualified cves columns and must not collide with the join below.
    cve_filter = ""
    params: list = []
    if stack_clause:
        cve_filter = f"WHERE m.cve_id IN (SELECT cve_id FROM cves WHERE {stack_clause})"
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
        """,
        params,
    )
    pack_rows = await db.execute_fetchall(
        "SELECT technique_id, COUNT(*) AS pack_count FROM hunt_packs GROUP BY technique_id"
    )
    technique_rows = await db.execute_fetchall(
        "SELECT technique_id, name, tactic, url FROM mitre_techniques"
    )
    case_study_counts = await get_case_study_counts_by_technique(db)

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
            "case_study_count": case_study_counts.get(tid, 0),
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
            "case_study_count": case_study_counts.get(tid, 0),
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


async def count_coverage_summary(db) -> dict[str, int]:
    """Lightweight covered/total technique counts, for tile-sized summaries
    (Security Architecture Overview's MITRE Detection Coverage tile) that
    only need two numbers -- doesn't build the full coverage map (CVE/KEV
    joins, per-technique metadata, sorting) just to throw away everything
    but the counts. Same "yours"/"community" status logic as
    build_coverage_map, just without the per-CVE detail."""
    technique_rows = await db.execute_fetchall(
        "SELECT DISTINCT technique_id FROM cve_technique_map"
    )
    total_ids = {r["technique_id"] for r in technique_rows}
    if not total_ids:
        return {"covered": 0, "total": 0}

    pack_rows = await db.execute_fetchall(
        "SELECT DISTINCT technique_id FROM hunt_packs"
    )
    packed_ids = {r["technique_id"] for r in pack_rows}

    covered = sum(
        1 for tid in total_ids
        if tid in packed_ids or _technique_prefix(tid) in _COMMUNITY_TECHNIQUES
    )
    return {"covered": covered, "total": len(total_ids)}


@router.get("/api/forge/coverage")
async def forge_coverage(
    stack: str | None = Query(
        default=None,
        max_length=500,
        description="Comma-separated stack terms (same matching as /api/cves)",
    ),
):
    db = await get_db()
    try:
        return await build_coverage_map(db, stack)
    finally:
        await db.close()


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

        # DC-4: composer without GitHub community fetch. Attach SigmaHQ from
        # local Postgres index when CVE-exact rules exist (U4) — never GitHub.
        evidence = await compose_detection_evidence(
            db,
            cve_id=cve_id,
            technique_ids=[technique_id],
            cwe_ids=cwe_ids,
            product=product,
            include_community=False,
        )
        composed = emit_composed_detection(
            evidence,
            description=description,
            cwe_ids=cwe_ids,
        )
        index_sigma = await find_index_rules_for_cve(db, cve_id, limit=1)
        if index_sigma and (index_sigma[0].get("content") or "").strip():
            sigma_yaml = index_sigma[0]["content"]
            compose_basis = "sigmahq_index"
        else:
            sigma_yaml = composed["generated_sigma"] or ""
            compose_basis = composed["compose_basis"]
        siem = dict(composed["siem_queries"] or {})
        log_patterns = siem.pop("log_patterns", [])
        evidence_summary = evidence.get("evidence_summary") or {}
        title = f"{cve_id} — {technique_name} hunt pack"

        existing = await db.execute_fetchall(
            "SELECT id FROM hunt_packs WHERE technique_id = ? AND cve_id = ?",
            (technique_id, cve_id),
        )
        created = not existing

        from db.timeutil import utcnow_str
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

    pack = _pack_to_dict(pack_rows[0])
    # cve was already loaded above for sigma/SIEM generation — reuse it for
    # the same CWE/EPSS/KEV fields list_hunt_packs and get_hunt_pack expose,
    # so a freshly generated pack shows them in the rail immediately instead
    # of only after the next full technique-detail reload (forge-redesign.md
    # §4 FR-3).
    pack["cwe_ids"] = cwe_ids
    pack["cvss_score"] = cve["cvss_score"]
    pack["epss_score"] = cve["epss_score"]
    pack["is_kev"] = bool(cve["is_kev"])

    return {
        "pack": pack,
        "created": created,
        "compose_basis": compose_basis,
        "evidence_summary": evidence_summary,
    }


# ── Hunt pack API (registered after the literal /generate sibling) ──

_VALID_PRIORITIES = frozenset({"low", "medium", "high", "critical"})


@router.get("/api/hunt-packs")
async def list_hunt_packs(
    technique_id: str | None = Query(default=None),
    cve_id: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List saved hunt packs (FR-1 Library view). Paginated, filterable."""
    conditions: list[str] = []
    params: list = []

    if technique_id:
        conditions.append("technique_id = ?")
        params.append(_validate_technique_id(technique_id))
    if cve_id:
        conditions.append("cve_id = ?")
        params.append(cve_id.strip().upper())
    if priority:
        p = priority.strip().lower()
        if p not in _VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority filter")
        conditions.append("priority = ?")
        params.append(p)
    if q and q.strip():
        conditions.append("LOWER(title) LIKE ?")
        params.append(f"%{q.strip().lower()}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    db = await get_db()
    try:
        count_rows = await db.execute_fetchall(
            f"SELECT COUNT(*) AS cnt FROM hunt_packs {where}", params
        )
        total = count_rows[0]["cnt"] if count_rows else 0

        # Subquery keeps the existing filtered/paginated hunt_packs query
        # untouched (params list stays identical); the outer join only adds
        # cves columns for the Library view (forge-redesign.md §3.1/§4) —
        # is_kev (FR-1), cwe_ids/cvss_score/epss_score (FR-3), all already
        # selected by the pack-generate flow, no extra query added here.
        rows = await db.execute_fetchall(
            f"""
            SELECT hp.*, c.is_kev AS cve_is_kev, c.cwe_ids AS cve_cwe_ids,
                   c.cvss_score AS cve_cvss_score, c.epss_score AS cve_epss_score
            FROM (
                SELECT * FROM hunt_packs {where}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ) hp
            LEFT JOIN cves c ON c.cve_id = hp.cve_id
            ORDER BY hp.updated_at DESC
            """,
            params + [limit, offset],
        )
    finally:
        await db.close()

    packs = []
    for r in rows:
        pack = _pack_to_dict(r)
        pack["is_kev"] = bool(r["cve_is_kev"])
        pack["cwe_ids"] = _loads_or(r["cve_cwe_ids"], [])
        pack["cvss_score"] = r["cve_cvss_score"]
        pack["epss_score"] = r["cve_epss_score"]
        packs.append(pack)

    return {"packs": packs, "total": total}


@router.delete("/api/hunt-packs/{pack_id}")
async def delete_hunt_pack(pack_id: int, request: Request):
    """Delete one saved hunt pack; writes an audit_log entry attributed to
    the authenticated analyst (request.state.user_username, populated by
    the session_auth_middleware -> require_user gate on all /api/* routes)."""
    from dependencies import audit

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT technique_id, cve_id FROM hunt_packs WHERE id = ?", (pack_id,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Hunt pack not found")
        pack = rows[0]

        await db.execute("DELETE FROM hunt_packs WHERE id = ?", (pack_id,))
        await db.commit()
    finally:
        await db.close()

    await audit(request, "hunt_pack_deleted", f"{pack['technique_id']}/{pack['cve_id']}")

    return {"ok": True}


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
        linked_count_rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS cnt FROM cve_technique_map WHERE technique_id = ?",
            (tid,),
        )
        linked_cve_total = int(linked_count_rows[0]["cnt"] or 0) if linked_count_rows else 0
        cve_rows = await db.execute_fetchall(
            """
            SELECT c.cve_id, c.severity, c.cvss_score, c.epss_score,
                   c.is_kev, c.published, c.cwe_ids, c.description
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
        case_studies = await get_case_studies_for_technique(db, tid)
    finally:
        await db.close()

    # cve_rows above is already fetched for "linked CVEs" — reuse it to
    # attach CWE/EPSS/CVSS to each saved pack's header (forge-redesign.md
    # §4) without a second query.
    cve_meta = {
        r["cve_id"]: {
            "cwe_ids": _loads_or(r["cwe_ids"], []),
            "cvss_score": r["cvss_score"],
            "epss_score": r["epss_score"],
        }
        for r in cve_rows
    }

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

    packs = []
    for r in pack_rows:
        pack = _pack_to_dict(r)
        meta = cve_meta.get(pack["cve_id"], {})
        pack["cwe_ids"] = meta.get("cwe_ids", [])
        pack["cvss_score"] = meta.get("cvss_score")
        pack["epss_score"] = meta.get("epss_score")
        packs.append(pack)

    return {
        "technique": technique,
        "status": _coverage_status(len(pack_rows), tid),
        "packs": packs,
        "siem_queries": baseline,
        "log_patterns": log_patterns,
        "case_studies": case_studies,
        "linked_cve_total": linked_cve_total,
        "linked_cves": [
            {
                "cve_id": r["cve_id"],
                "severity": r["severity"],
                "cvss_score": r["cvss_score"],
                "epss_score": r["epss_score"],
                "is_kev": bool(r["is_kev"]),
                "published": r["published"],
                "description": ((r["description"] or "")[:180]),
            }
            for r in cve_rows
        ],
    }
