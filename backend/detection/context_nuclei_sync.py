"""Scheduler-side Nuclei artifact enrichment for DetectionContext (Sprint D4)."""

from __future__ import annotations

import logging
import os

import aiosqlite

from detection.artifact_extract import fetch_nuclei_template_text
from detection.context import (
    build_detection_context,
    get_detection_context,
    set_detection_context,
    _parse_cwe_ids,
)
from detection.nuclei_parser import parse_nuclei_template_yaml

logger = logging.getLogger(__name__)

NUCLEI_PROVIDER = "briefr-nuclei"


def detection_context_nuclei_enabled() -> bool:
    return os.environ.get("DETECTION_CONTEXT_NUCLEI_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def get_detection_context_nuclei_max_per_run() -> int:
    try:
        return int(os.environ.get("DETECTION_CONTEXT_NUCLEI_MAX_PER_RUN", "50"))
    except ValueError:
        return 50


def _merge_artifacts(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()

    def _key(art: dict) -> str:
        return "|".join(
            [
                ",".join(art.get("paths") or []),
                ",".join(art.get("params") or []),
                ",".join(art.get("keywords") or []),
                str(art.get("method") or ""),
            ]
        )

    for art in (existing or []) + (incoming or []):
        if not isinstance(art, dict):
            continue
        key = _key(art)
        if key in seen:
            continue
        seen.add(key)
        merged.append(art)
    return merged[:8]


async def enrich_detection_context_from_nuclei(
    db: aiosqlite.Connection,
    *,
    cve_id: str,
    description: str = "",
    cwe_ids: list[str] | None = None,
    technique_id: str = "",
    affected_products=None,
    exploits: list[dict],
) -> bool:
    """Fetch Nuclei YAML for CVE exploits, parse artifacts, merge into cache."""
    nuclei_exploits = [
        exp
        for exp in exploits
        if str(exp.get("source") or "").lower() == "nuclei" and exp.get("url")
    ]
    if not nuclei_exploits:
        return False

    parsed_artifacts: list[dict] = []
    for exp in nuclei_exploits[:3]:
        yaml_text = await fetch_nuclei_template_text(str(exp.get("url") or ""))
        if not yaml_text:
            continue
        parsed_artifacts.extend(parse_nuclei_template_yaml(yaml_text))
        if parsed_artifacts:
            break

    if not parsed_artifacts:
        return False

    existing = await get_detection_context(db, cve_id)
    if existing:
        base_ctx = dict(existing)
    else:
        base_ctx = build_detection_context(
            cve_id=cve_id,
            cwe_ids=cwe_ids,
            technique_id=technique_id,
            affected_products=affected_products,
        )

    base_ctx["artifacts"] = _merge_artifacts(
        base_ctx.get("artifacts") or [],
        parsed_artifacts,
    )
    base_ctx["provider"] = NUCLEI_PROVIDER
    base_ctx["model"] = "nuclei-parser"
    await set_detection_context(db, cve_id, base_ctx)
    return True


async def run_detection_context_nuclei_for_cves(
    db: aiosqlite.Connection,
    cve_ids: list[str],
    *,
    progress_cb=None,
) -> dict[str, int]:
    """Parse Nuclei templates for touched CVEs after exploit_sync."""
    from database import read_cve_exploits_from_db

    stats = {"candidates": 0, "written": 0, "skipped": 0, "errors": 0}
    limit = get_detection_context_nuclei_max_per_run()
    unique = []
    seen: set[str] = set()
    for raw in cve_ids:
        cve = (raw or "").strip().upper()
        if not cve or cve in seen:
            continue
        seen.add(cve)
        unique.append(cve)
        if len(unique) >= limit:
            break

    stats["candidates"] = len(unique)
    if not unique:
        return stats

    for index, cve_id in enumerate(unique, start=1):
        if progress_cb:
            progress_cb(
                f"DetectionContext Nuclei: {index}/{len(unique)} ({cve_id})"
            )
        try:
            rows = await db.execute_fetchall(
                """
                SELECT description, affected_products, cwe_ids, mitre_technique
                FROM cves
                WHERE cve_id = ?
                """,
                (cve_id,),
            )
            if not rows:
                stats["skipped"] += 1
                continue
            row = dict(rows[0])
            exploits = await read_cve_exploits_from_db(
                db, cve_id, max_age_hours=24 * 365
            )
            if not exploits:
                stats["skipped"] += 1
                continue
            wrote = await enrich_detection_context_from_nuclei(
                db,
                cve_id=cve_id,
                description=row.get("description") or "",
                cwe_ids=_parse_cwe_ids(row.get("cwe_ids")),
                technique_id=row.get("mitre_technique") or "",
                affected_products=row.get("affected_products"),
                exploits=exploits,
            )
            if wrote:
                stats["written"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            stats["errors"] += 1
            logger.error("DetectionContext Nuclei failed for %s: %s", cve_id, exc)

    return stats
