"""
MITRE ATT&CK Enterprise STIX + CTID CVE→technique mappings.
"""

from __future__ import annotations

import csv
import io
import json
import logging
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
        tactic = ""
        if phases:
            tactic = _format_tactic(phases[0].get("phase_name", ""))

        description = (obj.get("description") or "").strip()
        if len(description) > 500:
            description = description[:497] + "..."

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


def parse_cve_mappings_csv(text: str) -> dict[str, list[str]]:
    """Parse CTID Att&ckToCveMappings.csv → { CVE-ID: [Txxxx, ...] }."""
    mapping: dict[str, set[str]] = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        cve_id = (row.get("CVE ID") or row.get("CVE_ID") or "").strip().upper()
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
    cve_map: dict[str, list[str]] = {}
    try:
        logger.info("Downloading CTID CVE→ATT&CK mappings JSON from %s", CVE_MAPPINGS_JSON_URL)
        json_raw = await _fetch_bytes(CVE_MAPPINGS_JSON_URL)
        json_data = json.loads(json_raw)
        cve_map = parse_cve_mappings_json(json_data)
        logger.info("CVE mappings from JSON: %d CVEs", len(cve_map))
    except Exception as exc:
        logger.warning("CVE mappings JSON unavailable, using CSV fallback: %s", exc)

    if not cve_map:
        logger.info("Downloading CTID CVE→ATT&CK mappings CSV")
        csv_text = (await _fetch_bytes(CVE_MAPPINGS_CSV_URL)).decode("utf-8", errors="replace")
        cve_map = parse_cve_mappings_csv(csv_text)
        logger.info("CVE mappings from CSV: %d CVEs", len(cve_map))

    csv_map = cve_map

    kev_map: dict[str, list[str]] = {}
    try:
        logger.info("Downloading CTID KEV→ATT&CK mappings")
        kev_raw = await _fetch_bytes(KEV_ATTACK_MAPPINGS_URL)
        kev_data = json.loads(kev_raw)
        kev_map = parse_kev_attack_mappings(kev_data)
        logger.info("CVE mappings from KEV ATT&CK: %d CVEs", len(kev_map))
    except Exception as exc:
        logger.warning("KEV ATT&CK mapping fetch failed (non-fatal): %s", exc)

    merged = merge_cve_technique_maps(csv_map, kev_map)
    logger.info("Total unique CVE→technique mappings: %d CVEs", len(merged))
    return merged


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
    }
