"""Nuclei templates CVE index snapshot sync."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from database import replace_cve_exploits_by_source
from feeds.exploit_common import SOURCE_NUCLEI, normalize_cve_id, exploit_card
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

NUCLEI_CVES_URL = (
    "https://raw.githubusercontent.com/projectdiscovery/nuclei-templates/main/cves.json"
)


def parse_nuclei_cves_index(text: str) -> dict[str, list[dict]]:
    mapping: dict[str, list[dict]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        cve_id = normalize_cve_id(entry.get("ID") or "")
        if not cve_id:
            continue
        info = entry.get("Info") if isinstance(entry.get("Info"), dict) else {}
        title = (info.get("Name") or f"Nuclei template for {cve_id}").strip()
        file_path = (entry.get("file_path") or "").strip()
        url = (
            f"https://github.com/projectdiscovery/nuclei-templates/blob/main/{file_path}"
            if file_path
            else "https://github.com/projectdiscovery/nuclei-templates"
        )
        card = exploit_card(
            title=title,
            exploit_type="poc",
            source=SOURCE_NUCLEI,
            url=url,
            published_date="",
        )
        mapping.setdefault(cve_id, []).append(card)
    return mapping


async def fetch_nuclei_cves_index() -> str | None:
    try:
        response = await resilient_get("nuclei", NUCLEI_CVES_URL, timeout=180.0)
        await record_api_call("nuclei", 1)
        return response.text
    except CircuitOpenError:
        logger.warning("Nuclei circuit open — skipping cves.json download")
        return None
    except httpx.HTTPError as exc:
        logger.error("Nuclei cves.json download failed: %s", exc)
        return None


async def sync_nuclei(db, known_cve_ids: set[str]) -> dict[str, int]:
    stats = {"cves": 0, "rows": 0, "skipped": 0}
    if os.environ.get("NUCLEI_SYNC_ENABLED", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        stats["skipped"] = 1
        return stats

    text = await fetch_nuclei_cves_index()
    if not text:
        return stats

    parsed = parse_nuclei_cves_index(text)
    filtered = {
        cve_id: cards
        for cve_id, cards in parsed.items()
        if cve_id in known_cve_ids
    }
    rows, cves = await replace_cve_exploits_by_source(db, SOURCE_NUCLEI, filtered)
    stats["rows"] = rows
    stats["cves"] = cves
    stats["touched"] = sorted(filtered.keys())
    return stats
