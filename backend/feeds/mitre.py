"""
MITRE ATT&CK Enterprise STIX + CTID CVE→technique mappings.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ENTERPRISE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)
CVE_MAPPINGS_JSON_URL = (
    "https://raw.githubusercontent.com/center-for-threat-informed-defense/"
    "mappings-explorer/main/src/mappings/NVD/attack-14.0/enterprise/CVE_mappings.json"
)
# Official CTID bulk CVE→ATT&CK file (spec CVE_mappings.json path 404 on GitHub as of 2026)
CVE_MAPPINGS_CSV_URL = (
    "https://raw.githubusercontent.com/center-for-threat-informed-defense/"
    "mappings-explorer/main/src/mapex_convert/mappings/Att%26ckToCveMappings.csv"
)
KEV_ATTACK_MAPPINGS_URL = (
    "https://raw.githubusercontent.com/center-for-threat-informed-defense/"
    "mappings-explorer/main/mappings/kev/attack-16.1/kev-07.28.2025/enterprise/"
    "kev-07.28.2025_attack-16.1-enterprise.json"
)

TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$", re.IGNORECASE)

# Columns in CTID CSV that hold semicolon-separated technique IDs
CVE_TECHNIQUE_COLUMNS = (
    "Primary Impact",
    "Secondary Impact",
    "Exploitation Technique",
    "Uncategorized",
)


def technique_url(technique_id: str) -> str:
    tid = technique_id.strip().upper()
    if "." in tid:
        base, sub = tid.split(".", 1)
        return f"https://attack.mitre.org/techniques/{base}/{sub}/"
    return f"https://attack.mitre.org/techniques/{tid}/"


def _format_tactic(phase_name: str) -> str:
    return phase_name.replace("-", " ").title()


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_detection_by_attack_pattern(data: dict) -> dict[str, str]:
    """Map attack-pattern STIX id → detection guidance from detection-strategy objects."""
    strategies = {
        o["id"]: o
        for o in data.get("objects", [])
        if o.get("type") == "x-mitre-detection-strategy"
    }
    by_ap: dict[str, list[str]] = {}
    for obj in data.get("objects", []):
        if obj.get("type") != "relationship" or obj.get("relationship_type") != "detects":
            continue
        src = obj.get("source_ref") or ""
        tgt = obj.get("target_ref") or ""
        strat = strategies.get(src) or strategies.get(tgt)
        if not strat:
            continue
        ap_ref = tgt if tgt.startswith("attack-pattern--") else src
        if not ap_ref.startswith("attack-pattern--"):
            continue
        chunk = (strat.get("description") or strat.get("name") or "").strip()
        if chunk:
            by_ap.setdefault(ap_ref, []).append(chunk)
    return {ap: _truncate(" ".join(parts), 400) for ap, parts in by_ap.items()}


def _normalize_technique_id(raw: str) -> str | None:
    tid = raw.strip().upper()
    if TECHNIQUE_ID_RE.match(tid):
        return tid
    return None


def _split_technique_field(value: str) -> list[str]:
    if not value or not str(value).strip():
        return []
    out: list[str] = []
    for part in str(value).replace(",", ";").split(";"):
        tid = _normalize_technique_id(part)
        if tid and tid not in out:
            out.append(tid)
    return out


async def _fetch_bytes(url: str, timeout: float = 180.0) -> bytes:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content


def parse_enterprise_attack_stix(data: dict) -> list[dict]:
    """Parse MITRE Enterprise ATT&CK STIX bundle into mitre_techniques rows."""
    techniques: dict[str, dict] = {}
    detection_by_ap = _build_detection_by_attack_pattern(data)

    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern" or obj.get("revoked"):
            continue
        if obj.get("x_mitre_deprecated"):
            continue

        technique_id = None
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id", "").startswith("T"):
                technique_id = _normalize_technique_id(ref["external_id"])
                break
        if not technique_id:
            continue

        phases = obj.get("kill_chain_phases") or []
        tactic_names: list[str] = []
        for phase in phases:
            name = _format_tactic(phase.get("phase_name", ""))
            if name and name not in tactic_names:
                tactic_names.append(name)
        tactic = ", ".join(tactic_names)

        description = _truncate(obj.get("description") or "", 500)
        detection = detection_by_ap.get(obj.get("id") or "", "")

        platforms = obj.get("x_mitre_platforms") or []
        if not isinstance(platforms, list):
            platforms = []

        techniques[technique_id] = {
            "technique_id": technique_id,
            "name": (obj.get("name") or technique_id).strip(),
            "description": description,
            "tactic": tactic,
            "url": technique_url(technique_id),
            "platforms": platforms,
            "detection": detection,
        }

    return list(techniques.values())


def parse_cve_mappings_json(data: Any) -> dict[str, list[str]]:
    """
    Parse CVE→ATT&CK JSON mapping file.
    Supports { "CVE-2021-44228": ["T1190", ...], ... } and list-of-objects forms.
    """
    mapping: dict[str, set[str]] = {}

    def add_pair(cve_id: str, tid_raw: str) -> None:
        tid = _normalize_technique_id(tid_raw)
        if not tid:
            return
        cve = cve_id.strip().upper()
        if not cve.startswith("CVE-"):
            return
        mapping.setdefault(cve, set()).add(tid)

    if isinstance(data, dict):
        for key, value in data.items():
            key_upper = str(key).strip().upper()
            if key_upper.startswith("CVE-"):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            add_pair(key_upper, item)
                        elif isinstance(item, dict):
                            add_pair(
                                key_upper,
                                item.get("technique_id")
                                or item.get("attack_object_id")
                                or item.get("id")
                                or "",
                            )
                elif isinstance(value, str):
                    for tid in _split_technique_field(value):
                        mapping.setdefault(key_upper, set()).add(tid)
            elif key in ("mappings", "cve_mappings", "data") and isinstance(value, list):
                for entry in value:
                    if not isinstance(entry, dict):
                        continue
                    cve_id = (
                        entry.get("cve_id")
                        or entry.get("cveID")
                        or entry.get("CVE ID")
                        or entry.get("capability_id")
                        or ""
                    )
                    tids = entry.get("technique_ids") or entry.get("techniques") or []
                    if isinstance(tids, list):
                        for tid in tids:
                            add_pair(str(cve_id), str(tid))
                    else:
                        tid = entry.get("technique_id") or entry.get("attack_object_id") or ""
                        add_pair(str(cve_id), str(tid))

    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            cve_id = (
                entry.get("cve_id")
                or entry.get("cveID")
                or entry.get("CVE ID")
                or entry.get("capability_id")
                or ""
            )
            tids = entry.get("technique_ids") or entry.get("techniques") or []
            if isinstance(tids, list):
                for tid in tids:
                    add_pair(str(cve_id), str(tid))
            else:
                tid = entry.get("technique_id") or entry.get("attack_object_id") or ""
                add_pair(str(cve_id), str(tid))

    return {cve: sorted(tids) for cve, tids in mapping.items()}


def _csv_field(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row:
            return row[name] or ""
        bom_key = f"\ufeff{name}"
        if bom_key in row:
            return row[bom_key] or ""
    return ""


def parse_cve_mappings_csv(text: str) -> dict[str, list[str]]:
    """Parse CTID Att&ckToCveMappings.csv → { CVE-ID: [Txxxx, ...] }."""
    text = text.lstrip("\ufeff")
    mapping: dict[str, set[str]] = {}
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames:
        reader.fieldnames = [
            (f or "").lstrip("\ufeff").strip() for f in reader.fieldnames
        ]
    for row in reader:
        cve_id = _csv_field(row, "CVE ID", "CVE_ID").strip().upper()
        if not cve_id.startswith("CVE-"):
            continue
        techniques: set[str] = set()
        for col in CVE_TECHNIQUE_COLUMNS:
            for tid in _split_technique_field(row.get(col, "")):
                techniques.add(tid)
        if techniques:
            if cve_id not in mapping:
                mapping[cve_id] = set()
            mapping[cve_id].update(techniques)

    return {cve: sorted(tids) for cve, tids in mapping.items()}


def parse_kev_attack_mappings(data: dict) -> dict[str, list[str]]:
    """Parse CTID KEV→ATT&CK enterprise mapping JSON."""
    mapping: dict[str, set[str]] = {}
    for obj in data.get("mapping_objects", []):
        cve_id = (obj.get("capability_id") or "").strip().upper()
        if not cve_id.startswith("CVE-"):
            continue
        tid = _normalize_technique_id(obj.get("attack_object_id") or "")
        if not tid:
            continue
        mapping.setdefault(cve_id, set()).add(tid)
    return {cve: sorted(tids) for cve, tids in mapping.items()}


def resolve_technique_id(tid: str, known_ids: set[str]) -> str | None:
    """Map a technique ID to a row in mitre_techniques (parent fallback for sub-techniques)."""
    normalized = _normalize_technique_id(tid)
    if not normalized:
        return None
    if normalized in known_ids:
        return normalized
    if "." in normalized:
        parent = normalized.split(".", 1)[0]
        if parent in known_ids:
            return parent
    return None


def merge_cve_technique_maps(*sources: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = {}
    for source in sources:
        for cve_id, tids in source.items():
            merged.setdefault(cve_id, set()).update(tids)
    return {cve: sorted(tids) for cve, tids in merged.items()}


async def download_enterprise_attack() -> list[dict]:
    logger.info("Downloading MITRE Enterprise ATT&CK STIX from %s", ENTERPRISE_ATTACK_URL)
    raw = await _fetch_bytes(ENTERPRISE_ATTACK_URL)
    data = json.loads(raw)
    techniques = parse_enterprise_attack_stix(data)
    logger.info("Parsed %d ATT&CK techniques from STIX", len(techniques))
    return techniques


async def download_cve_technique_mappings() -> dict[str, list[str]]:
    sources: list[dict[str, list[str]]] = []

    json_url = (
        os.environ.get("MITRE_CVE_MAPPINGS_JSON_URL", "").strip()
        or CVE_MAPPINGS_JSON_URL
    )
    try:
        logger.info("Downloading CVE→ATT&CK mappings JSON from %s", json_url)
        json_data = json.loads(await _fetch_bytes(json_url))
        json_map = parse_cve_mappings_json(json_data)
        logger.info("CVE mappings from JSON: %d CVEs", len(json_map))
        if json_map:
            sources.append(json_map)
    except Exception as exc:
        logger.warning("CVE mappings JSON unavailable (%s), using CSV/KEV sources", exc)

    try:
        logger.info("Downloading CTID CVE→ATT&CK mappings CSV from mappings-explorer")
        csv_text = (await _fetch_bytes(CVE_MAPPINGS_CSV_URL)).decode(
            "utf-8-sig", errors="replace"
        )
        csv_map = parse_cve_mappings_csv(csv_text)
        logger.info("CVE mappings from CTID CSV: %d CVEs", len(csv_map))
        if csv_map:
            sources.append(csv_map)
    except Exception as exc:
        logger.warning("CTID CSV mapping fetch failed (non-fatal): %s", exc)

    kev_map: dict[str, list[str]] = {}
    try:
        logger.info("Downloading CTID KEV→ATT&CK mappings")
        kev_raw = await _fetch_bytes(KEV_ATTACK_MAPPINGS_URL)
        kev_data = json.loads(kev_raw)
        kev_map = parse_kev_attack_mappings(kev_data)
        logger.info("CVE mappings from KEV ATT&CK: %d CVEs", len(kev_map))
        if kev_map:
            sources.append(kev_map)
    except Exception as exc:
        logger.warning("KEV ATT&CK mapping fetch failed (non-fatal): %s", exc)

    merged = merge_cve_technique_maps(*sources) if sources else {}
    logger.info("Total unique CVE→technique mappings: %d CVEs", len(merged))
    return merged


async def cve_technique_from_db_column(db) -> dict[str, list[str]]:
    """Supplement CTID mappings with mitre_technique values already on CVE rows."""
    rows = await db.execute_fetchall(
        """
        SELECT cve_id, mitre_technique
        FROM cves
        WHERE mitre_technique IS NOT NULL AND TRIM(mitre_technique) != ''
        """
    )
    mapping: dict[str, set[str]] = {}
    for row in rows:
        cve_id = row["cve_id"]
        tid = _normalize_technique_id(row["mitre_technique"] or "")
        if tid:
            mapping.setdefault(cve_id, set()).add(tid)
    return {cve: sorted(tids) for cve, tids in mapping.items()}


async def refresh_mitre_data(db) -> dict[str, int]:
    """
    Refresh mitre_techniques and cve_technique_map tables.
    Returns counts: techniques, cve_mappings, cve_links_inserted.
    """
    from database import (
        clear_cve_technique_map,
        get_all_cve_ids_set,
        replace_mitre_techniques,
        upsert_cve_technique_pairs,
    )

    techniques = await download_enterprise_attack()
    cve_map = await download_cve_technique_mappings()
    db_column_map = await cve_technique_from_db_column(db)
    if db_column_map:
        cve_map = merge_cve_technique_maps(cve_map, db_column_map)
        logger.info(
            "Added %d CVEs from mitre_technique column; merged total %d CVEs",
            len(db_column_map),
            len(cve_map),
        )

    # Clear mappings before replacing techniques (FK: map.technique_id → mitre_techniques)
    await clear_cve_technique_map(db)
    await replace_mitre_techniques(db, techniques)

    known_technique_ids = {t["technique_id"] for t in techniques}
    known_cves = await get_all_cve_ids_set(db)
    pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    skipped_unknown = 0

    for cve_id, tids in cve_map.items():
        if cve_id not in known_cves:
            continue
        for tid in tids:
            resolved = resolve_technique_id(tid, known_technique_ids)
            if not resolved:
                skipped_unknown += 1
                continue
            key = (cve_id, resolved)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            pairs.append(key)

    if skipped_unknown:
        logger.info(
            "Skipped %d CVE→technique links (technique not in Enterprise STIX)",
            skipped_unknown,
        )

    inserted = await upsert_cve_technique_pairs(db, pairs)
    await db.commit()

    return {
        "techniques": len(techniques),
        "cve_mappings_source": len(cve_map),
        "cve_links": inserted,
        "skipped_unknown_techniques": skipped_unknown,
        "mapping_sources": "ctid_csv+kev_json+db_column",
    }
