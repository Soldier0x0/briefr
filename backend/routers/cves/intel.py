"""CVE router package.

Split from `routers.cves` (F1.2) without changing route registration order or
handler behavior.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request

from correlation.engine import get_correlation_for_cve
from correlation.feedback import add_feedback, load_feedback, remove_feedback
from correlation.suppressions import add_suppression, load_suppressions, remove_suppression
from database import delete_feed_cache_prefix, get_db, write_audit_log
from detection.composer import compose_detection_evidence, emit_composed_detection
from feeds.extended import greynoise_scans_for_cve, load_public_exploits_for_cve
from intel.provenance import (
    derive_correlation_provenance,
    derive_detection_provenance,
    otx_configured_from_env,
)
from read_cache import DEFAULT_TTL_SECONDS, cached_read
from routers._validators import require_cve_id
from scoring.asset_match import cpe_match_score_for_cve, profile_to_match_assets
from scoring.environment import classify_environment
from scoring.priority import derive_operational_priority, extract_profile_exposure_flags
from scoring.risk import calculate_momentum, calculate_risk_score
from scoring.ssvc import calculate_ssvc_outcome
from scoring.threat import calculate_threat_score

from .common import row_to_cve_dict
from .models import CorrelationFeedbackBody, CorrelationSuppressBody, RiskScoreRequest

logger = logging.getLogger(__name__)
intel_router = APIRouter()


@intel_router.post("/api/cves/{cve_id}/risk")
async def cve_risk_score(cve_id: str, body: RiskScoreRequest | None = None):
    """
    Operational Priority surface for one CVE (ADR-002).

    Returns Threat Score, Environment tier, Operational Priority band, and
    legacy Risk Score v1.1b under ``legacy_risk_v11b``. Computes momentum and
    optional correlation escalation server-side.
    """
    cve_id = require_cve_id(cve_id)

    body = body or RiskScoreRequest()
    cve_key = cve_id

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT c.cve_id, c.description, c.cvss_score, c.severity, c.published,
                   c.modified, c.affected_products, c.summary, c.is_kev, c.epss_score, c.epss_percentile,
                   c.has_poc, c.source_urls, c.cpe_matches,
                   k.date_added AS kev_date_added,
                   k.due_date AS kev_due_date
            FROM cves c
            LEFT JOIN kev_deadlines k ON k.cve_id = c.cve_id
            WHERE c.cve_id = ?
            """,
            (cve_key,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

        cve = row_to_cve_dict(rows[0])
        cpe_raw = rows[0]["cpe_matches"]
        if cpe_raw and isinstance(cpe_raw, str):
            try:
                cve["cpe_matches"] = json.loads(cpe_raw)
            except (json.JSONDecodeError, TypeError):
                cve["cpe_matches"] = []
        else:
            cve["cpe_matches"] = cpe_raw or []

        try:
            cve["public_exploits"] = await load_public_exploits_for_cve(
                db,
                cve_key,
                has_poc=bool(cve.get("has_poc")),
                source_urls=cve.get("source_urls"),
            )
        except Exception as exc:
            logger.error("Exploit load failed for risk score %s: %s", cve_id, exc)
            cve["public_exploits"] = []
            try:
                await db.rollback()
            except Exception:
                pass

        momentum = await calculate_momentum(cve_key, db)

        profile = body.profile if body.profile else None
        assets = [a.model_dump() for a in body.assets if a.product.strip()]
        if profile and not assets:
            assets = profile_to_match_assets(profile)

        backend_match = None
        if profile and assets:
            backend_match = cpe_match_score_for_cve(cve, assets)

        mom_score = momentum.get("momentum_score", 0.0)
        legacy_risk = calculate_risk_score(
            cve,
            profile=profile,
            backend_match_score=backend_match,
            momentum_score=mom_score,
        )
        threat = calculate_threat_score(cve, momentum_score=mom_score)
        environment = classify_environment(cve, profile, backend_match)
        # E1-2 / ADR-004: OP hero uses cheap signals only on this path.
        # Correlation-based escalation is applied client-side when correlation
        # data arrives (or from precomputed snapshots on the correlation route).
        try:
            await db.commit()
        except Exception as exc:
            logger.warning("Failed to commit risk score transaction: %s", exc)
            try:
                await db.rollback()
            except Exception:
                pass
        # W3: additive EPSS OP escalations (Threat formula unchanged; KEV dominance intact)
        mom_signals = momentum.get("momentum_signals") or []
        epss_rising = any(
            isinstance(sig, dict) and sig.get("type") == "epss_rising"
            for sig in mom_signals
        )
        # W5: optional profile exposure flags → OP modifiers + SSVC factors only.
        flags = extract_profile_exposure_flags(profile)
        operational_priority = derive_operational_priority(
            threat.get("band", "LOW"),
            environment.get("tier", "UNKNOWN"),
            corr_escalation=False,
            epss=cve.get("epss_score"),
            epss_rising=epss_rising,
            internet_facing=flags["internet_facing"],
            criticality=flags["criticality"],
            is_kev=bool(cve.get("is_kev")),
        )
        # W4: SSVC annotation parallel to OP — does not mutate Threat or OP.
        ssvc = calculate_ssvc_outcome(
            threat=threat,
            environment=environment,
            cve=cve,
            internet_facing=flags["internet_facing"],
            criticality=flags["criticality"],
            privileged_service=flags["privileged_service"],
            ot_safety=flags["ot_safety"],
        )
    finally:
        await db.close()

    return {
        "cve_id": cve_key,
        "threat": threat,
        "environment": environment,
        "operational_priority": operational_priority,
        "ssvc": ssvc,
        "legacy_risk_v11b": legacy_risk,
        "momentum": momentum,
        "hasProfile": legacy_risk.get("hasProfile", False),
        "momentumScore": mom_score,
    }


@intel_router.get("/api/cves/{cve_id}/momentum")
async def cve_momentum(cve_id: str):
    """
    Compute momentum score (0–1) from EPSS trend and OTX pulse recency.
    Returns momentum_score and momentum_signals list for drawer breakdown.
    """
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        result = await calculate_momentum(cve_id, db)
    finally:
        await db.close()
    return result


@intel_router.get("/api/cves/{cve_id}/detection")
async def cve_detection(
    cve_id: str,
    product: str = Query(default="", description="Affected product name for rule title generation"),
):
    """
    Detection engineering resource for a CVE.
    Returns:
    - sigma_rules: community Sigma rules from SigmaHQ (cached 24h; match_basis + DRL attribution)
    - elastic_rules: community Elastic detection rules (cached 24h)
    - generated_sigma: optional BRIEFR class template YAML — omitted when community
      rules exist or the template would be generic
    - generated_sigma_meta: briefr_basis, briefr_class, confidence, status, optional suppressed
    - sigmahq_index: local index freshness (rules_active, synced_at) for honest empty UI
    - siem_queries: 4-platform quick-search queries (Elastic/Splunk/Sentinel/QRadar)
    - log_patterns: plain-English detection patterns from ATT&CK guidance
    """
    cve_id = require_cve_id(cve_id)

    github_token = os.environ.get("GITHUB_TOKEN", "")
    cve_upper = cve_id

    technique_ids: list[str] = []
    sigma_rules: list = []
    elastic_rules: list = []
    has_community_rules = False
    generated_sigma = None
    generated_sigma_meta = None
    detection_context = None
    siem_queries: dict = {}
    yara_rules: list = []
    evidence: dict | None = None
    detection_provenance = None
    sigmahq_index_status: dict = {
        "rules_active": 0,
        "synced_at": "",
        "ok": False,
    }
    db = await get_db()
    try:
        # Get CVE metadata for context
        row = await db.execute_fetchall(
            "SELECT description, mitre_technique, cwe_ids FROM cves WHERE cve_id = ?",
            (cve_upper,),
        )
        cve_desc = ""
        primary_technique = ""
        cwe_ids: list[str] = []
        if row:
            cve_desc = row[0]["description"] or ""
            primary_technique = row[0]["mitre_technique"] or ""
            raw_cwe = row[0]["cwe_ids"]
            if raw_cwe:
                try:
                    parsed = json.loads(raw_cwe) if isinstance(raw_cwe, str) else raw_cwe
                    if isinstance(parsed, list):
                        cwe_ids = [str(c) for c in parsed if str(c).strip()]
                except (json.JSONDecodeError, TypeError):
                    cwe_ids = []

        # Get all linked techniques
        tech_rows = await db.execute_fetchall(
            "SELECT technique_id FROM cve_technique_map WHERE cve_id = ?",
            (cve_upper,),
        )
        technique_ids = [r["technique_id"] for r in tech_rows]
        if primary_technique and primary_technique not in technique_ids:
            technique_ids.insert(0, primary_technique)

        # Shared evidence pack (DC-1) — community / Nuclei artifacts / YARA.
        # Sequential on one connection (asyncpg is single-flight per conn).
        evidence = await compose_detection_evidence(
            db,
            cve_id=cve_upper,
            technique_ids=technique_ids,
            cwe_ids=cwe_ids,
            product=product.strip(),
            github_token=github_token,
            include_community=True,
        )
        await db.commit()

        sigma_rules = evidence["community"]["sigma_rules"]
        elastic_rules = evidence["community"]["elastic_rules"]
        has_community_rules = evidence["community"]["has_community_rules"]
        detection_context = evidence.get("detection_context")

        composed = emit_composed_detection(
            evidence,
            description=cve_desc[:200] if cve_desc else "",
            cwe_ids=cwe_ids,
        )
        generated_sigma = composed["generated_sigma"]
        generated_sigma_meta = composed["generated_sigma_meta"]
        siem_queries = composed["siem_queries"]
        yara_rules = composed["yara_rules"]

        detection_provenance = await derive_detection_provenance(
            db,
            cve_upper,
            technique_ids=technique_ids,
        )

        try:
            from detection.sigmahq_index import get_sigmahq_index_status

            full = await get_sigmahq_index_status(db)
            sigmahq_index_status = {
                "rules_active": int(full.get("rules_active") or 0),
                "synced_at": full.get("synced_at") or "",
                "ok": bool(full.get("ok")),
                "commit_sha": full.get("commit_sha") or "",
            }
        except Exception:
            pass

    except Exception as exc:
        logger.exception("Detection lookup failed for %s", cve_upper)
        raise HTTPException(
            status_code=500,
            detail="Detection lookup failed",
        ) from exc
    finally:
        await db.close()

    return {
        "cve_id": cve_upper,
        "technique_ids": technique_ids[:5],
        "sigma_rules": sigma_rules,
        "elastic_rules": elastic_rules,
        "has_community_rules": has_community_rules,
        "generated_sigma": generated_sigma,
        "generated_sigma_meta": generated_sigma_meta,
        "detection_context": detection_context,
        "siem_queries": siem_queries,
        "yara_rules": yara_rules,
        "evidence": evidence,
        "provenance": detection_provenance,
        "sigmahq_index": sigmahq_index_status,
    }


@intel_router.get("/api/cves/{cve_id}/correlation")
async def cve_correlation(
    cve_id: str,
    sector: str = Query(default="", description="User's declared industry sector for actor matching"),
):
    """
    On-demand correlation for a CVE.
    Level 1: shared exploitation indicators with other CVEs (OTX pulse IOCs).
    Level 2: ATT&CK groups linked to this CVE's techniques, matched against user sector.
    Level 3: temporal vendor volume anomalies (pre-computed nightly).
    v2: pulse-centric campaign clusters with evidence receipts.
    Results are cached for 6 hours.
    """
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        result = await get_correlation_for_cve(
            db, cve_id, user_sector=sector.strip()
        )
        result["provenance"] = derive_correlation_provenance(
            result,
            otx_configured=otx_configured_from_env(),
        )
        await db.commit()
    finally:
        await db.close()

    return result


@intel_router.get("/api/cves/{cve_id}/greynoise-scans")
async def cve_greynoise_scans(cve_id: str):
    """
    On-demand GreyNoise scanning context for IPs mentioned in this CVE.
    Not called on drawer open — preserves the 50/week Community API quota.
    """
    cve_id = require_cve_id(cve_id)

    greynoise_key = os.environ.get("GREYNOISE_API_KEY", "")
    if not greynoise_key:
        return {"configured": False, "scans": []}

    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT description, source_urls FROM cves WHERE cve_id = ?",
            (cve_id,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")
        row = rows[0]
        source_urls = row["source_urls"]
        if source_urls and isinstance(source_urls, str):
            try:
                source_urls = json.loads(source_urls)
            except (json.JSONDecodeError, TypeError):
                source_urls = []
        scans = await greynoise_scans_for_cve(
            db,
            row["description"],
            source_urls if isinstance(source_urls, list) else [],
            greynoise_key,
        )
        await db.commit()
    finally:
        await db.close()

    return {"configured": True, "scans": scans}


@intel_router.get("/api/cves/{cve_id}/correlation/suppressions")
async def list_correlation_suppressions_for_cve(cve_id: str):
    """List persisted correlation suppressions for analyst review / restore."""
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        rows = await load_suppressions(db, cve_id)
    finally:
        await db.close()

    return {"cve_id": cve_id.upper(), "suppressions": rows}


@intel_router.post("/api/cves/{cve_id}/correlation/suppress")
async def suppress_correlation_finding(cve_id: str, body: CorrelationSuppressBody):
    """Dismiss a correlation finding for this CVE (persisted across rebuilds)."""
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        row = await add_suppression(
            db,
            cve_id,
            body.scope.strip(),
            body.key,
            body.reason.strip(),
            body.dismissed_by.strip(),
        )
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()

    return {"ok": True, "suppression": row}


@intel_router.delete("/api/cves/{cve_id}/correlation/suppress")
async def unsuppress_correlation_finding(
    cve_id: str,
    scope: str = Query(...),
    cve_id_b: str = Query(default=""),
    campaign_id: str = Query(default=""),
    pulse_id: str = Query(default=""),
):
    """Remove a correlation suppression."""
    cve_id = require_cve_id(cve_id)

    key: dict = {}
    if scope == "campaign_id":
        key = {"campaign_id": campaign_id}
    elif scope == "cve_pair":
        key = {"cve_id_b": cve_id_b}
    elif scope == "pulse_id":
        key = {"pulse_id": pulse_id}
    elif scope == "infrastructure":
        key = {"cve_id_b": cve_id_b}

    db = await get_db()
    try:
        removed = await remove_suppression(db, cve_id, scope, key)
        if not removed:
            raise HTTPException(status_code=404, detail="Suppression not found")
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    finally:
        await db.close()

    return {"ok": True}


@intel_router.get("/api/cves/{cve_id}/correlation/feedback")
async def list_correlation_feedback_for_cve(cve_id: str):
    """List persisted analyst feedback for correlation findings."""
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        rows = await load_feedback(db, cve_id)
    finally:
        await db.close()

    return {"cve_id": cve_id.upper(), "feedback": rows}


@intel_router.post("/api/cves/{cve_id}/correlation/feedback")
async def add_correlation_feedback(cve_id: str, body: CorrelationFeedbackBody, request: Request):
    """Record analyst confirm/reject feedback for a correlation finding."""
    cve_id = require_cve_id(cve_id)

    db = await get_db()
    try:
        row = await add_feedback(
            db,
            cve_id,
            body.scope.strip(),
            body.key,
            body.verdict.strip(),
            body.reason.strip(),
            body.created_by.strip(),
        )
        actor = getattr(request.state, "user_username", None) or body.created_by.strip() or ""
        await write_audit_log(
            db,
            actor,
            f"correlation.feedback.{row['verdict']}",
            f"{cve_id.upper()}:{body.scope}:{row['scope_key']}",
        )
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()

    return {"ok": True, "feedback": row}


@intel_router.delete("/api/cves/{cve_id}/correlation/feedback")
async def remove_correlation_feedback(
    cve_id: str,
    request: Request,
    scope: str = Query(...),
    verdict: str = Query(...),
    cve_id_b: str = Query(default=""),
    campaign_id: str = Query(default=""),
    pulse_id: str = Query(default=""),
):
    """Remove analyst correlation feedback."""
    cve_id = require_cve_id(cve_id)

    key: dict = {}
    if scope == "campaign_id":
        key = {"campaign_id": campaign_id}
    elif scope == "cve_pair":
        key = {"cve_id_b": cve_id_b}
    elif scope == "pulse_id":
        key = {"pulse_id": pulse_id}
    elif scope == "infrastructure":
        key = {"cve_id_b": cve_id_b}

    db = await get_db()
    try:
        removed = await remove_feedback(db, cve_id, scope, key, verdict)
        if not removed:
            raise HTTPException(status_code=404, detail="Feedback not found")
        actor = getattr(request.state, "user_username", None) or ""
        await write_audit_log(
            db,
            actor,
            "correlation.feedback.delete",
            f"{cve_id.upper()}:{scope}:{verdict}",
        )
        await delete_feed_cache_prefix(db, f"correlation:v2:{cve_id}")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await db.close()

    return {"ok": True}


@intel_router.get("/api/kev/deadlines")
async def kev_deadlines(
    sort: str = Query(default="recent", description="Sort order: recent (by dateAdded DESC) or urgent (by dueDate ASC)"),
    limit: int = Query(default=500, ge=1, le=2000, description="Maximum rows returned"),
):
    order_clause = (
        "ORDER BY date_added DESC"
        if sort == "recent"
        else "ORDER BY due_date ASC"
    )
    cache_key = f"kev_deadlines:{sort}:{limit}"

    async def build():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                f"""
                SELECT cve_id, product, short_description, required_action, due_date,
                       date_added, vendor_project, vulnerability_name,
                       known_ransomware, cwes, updated_at
                FROM kev_deadlines
                {order_clause}
                LIMIT ?
                """,
                (limit,),
            )
        finally:
            await db.close()

        entries = []
        for row in rows:
            entry = dict(row)
            try:
                parsed_cwes = json.loads(entry.get("cwes") or "[]")
                entry["cwes"] = parsed_cwes if isinstance(parsed_cwes, list) else []
            except (json.JSONDecodeError, TypeError):
                entry["cwes"] = []
            entry["ransomware_use"] = (
                str(entry.get("known_ransomware") or "").strip().lower() == "known"
            )
            entries.append(entry)

        return {"data": entries}

    return await cached_read(cache_key, DEFAULT_TTL_SECONDS, build)
