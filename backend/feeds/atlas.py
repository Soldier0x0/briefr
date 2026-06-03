"""
MITRE ATLAS — AI/ML adversarial threat landscape (separate from Enterprise ATT&CK).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

ATLAS_YAML_URL = os.environ.get(
    "ATLAS_YAML_URL",
    "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml",
)
ATLAS_CASE_STUDIES_DIR_URL = (
    "https://api.github.com/repos/mitre-atlas/atlas-data/contents/data/case-studies"
)

TECHNIQUE_ID_RE = re.compile(r"^AML\.T\d{4}(?:\.\d{3})?$", re.IGNORECASE)
CVE_ID_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


def atlas_technique_url(technique_id: str) -> str:
    tid = technique_id.strip().upper()
    return f"https://atlas.mitre.org/techniques/{tid}"


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_tactic_name(tactic_id: str, tactic_names: dict[str, str]) -> str:
    if tactic_id in tactic_names:
        return tactic_names[tactic_id]
    return tactic_id.replace("AML.TA", "").replace("-", " ").strip() or tactic_id


def _normalize_technique_id(raw: str) -> str | None:
    tid = (raw or "").strip().upper()
    if TECHNIQUE_ID_RE.match(tid):
        return tid
    return None


def extract_cve_ids(*texts: str | None) -> list[str]:
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in CVE_ID_RE.finditer(str(text)):
            found.add(match.group(0).upper())
    return sorted(found)


async def _fetch_bytes(url: str, timeout: float = 180.0) -> bytes:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content


def parse_atlas_yaml(data: dict) -> tuple[list[dict], list[dict]]:
    """Parse ATLAS.yaml into technique rows and case study rows."""
    matrix = (data.get("matrices") or [{}])[0]
    tactic_names: dict[str, str] = {}
    for tactic in matrix.get("tactics") or []:
        if tactic.get("object-type") == "tactic" and tactic.get("id"):
            tactic_names[tactic["id"]] = (tactic.get("name") or tactic["id"]).strip()

    techniques_out: list[dict] = []
    seen_techniques: set[str] = set()

    for tech in matrix.get("techniques") or []:
        if tech.get("object-type") != "technique":
            continue
        technique_id = _normalize_technique_id(tech.get("id") or "")
        if not technique_id or technique_id in seen_techniques:
            continue
        seen_techniques.add(technique_id)

        tactic_ids = tech.get("tactics") or []
        tactic_label = ""
        if tactic_ids:
            primary = tactic_ids[0]
            tactic_label = _format_tactic_name(primary, tactic_names)
        elif tech.get("specializes"):
            parent = _normalize_technique_id(tech.get("specializes") or "")
            for other in matrix.get("techniques") or []:
                if other.get("id") == parent:
                    pt = other.get("tactics") or []
                    if pt:
                        tactic_label = _format_tactic_name(pt[0], tactic_names)
                    break

        description = _truncate(tech.get("description") or "", 600)
        techniques_out.append(
            {
                "technique_id": technique_id,
                "name": (tech.get("name") or technique_id).strip(),
                "description": description,
                "tactic": tactic_label,
                "tactic_id": tactic_ids[0] if tactic_ids else "",
                "url": atlas_technique_url(technique_id),
            }
        )

    case_studies_out: list[dict] = []
    for study in data.get("case-studies") or []:
        if study.get("object-type") != "case-study":
            continue
        study_id = (study.get("id") or "").strip()
        if not study_id:
            continue

        procedure = study.get("procedure") or []
        technique_ids: list[str] = []
        proc_texts: list[str] = []
        for step in procedure:
            if isinstance(step, dict):
                tid = _normalize_technique_id(step.get("technique") or "")
                if tid and tid not in technique_ids:
                    technique_ids.append(tid)
                if step.get("description"):
                    proc_texts.append(str(step["description"]))

        ref_texts = []
        for ref in study.get("references") or []:
            if isinstance(ref, dict):
                ref_texts.append(str(ref.get("title") or ""))
                ref_texts.append(str(ref.get("url") or ""))

        summary_raw = study.get("summary") or ""
        cve_ids = extract_cve_ids(
            summary_raw,
            study.get("name") or "",
            *proc_texts,
            *ref_texts,
        )

        case_studies_out.append(
            {
                "study_id": study_id,
                "name": (study.get("name") or study_id).strip(),
                "summary": _truncate(summary_raw, 400),
                "summary_full": summary_raw.strip(),
                "techniques": technique_ids,
                "target": (study.get("target") or "AI / ML system").strip(),
                "date": (study.get("incident-date") or study.get("created_date") or "").strip(),
                "study_type": (study.get("case-study-type") or "").strip(),
                "cve_ids": cve_ids,
            }
        )

    return techniques_out, case_studies_out


async def download_atlas_bundle() -> tuple[list[dict], list[dict]]:
    logger.info("Downloading MITRE ATLAS from %s", ATLAS_YAML_URL)
    raw = await _fetch_bytes(ATLAS_YAML_URL)
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("---"):
        text = text.split("---", 1)[-1]
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("ATLAS.yaml did not parse to a mapping")
    techniques, case_studies = parse_atlas_yaml(data)
    logger.info("Parsed %d ATLAS techniques, %d case studies", len(techniques), len(case_studies))
    return techniques, case_studies


async def refresh_atlas_data(db) -> dict[str, int]:
    from database import replace_atlas_case_studies, replace_atlas_techniques

    techniques, case_studies = await download_atlas_bundle()
    await replace_atlas_techniques(db, techniques)
    await replace_atlas_case_studies(db, case_studies)
    await db.commit()
    return {
        "techniques": len(techniques),
        "case_studies": len(case_studies),
    }
