"""Metasploit module metadata snapshot sync."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from database import replace_cve_exploits_by_source
from feeds.exploit_common import SOURCE_METASPLOIT, extract_cve_ids, exploit_card
from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

METASPLOIT_METADATA_URL = (
    "https://raw.githubusercontent.com/rapid7/metasploit-framework/"
    "master/db/modules_metadata_base.json"
)


def parse_metasploit_metadata(payload: Any) -> dict[str, list[dict]]:
    if not isinstance(payload, dict):
        return {}
    mapping: dict[str, list[dict]] = {}
    for module in payload.values():
        if not isinstance(module, dict):
            continue
        if (module.get("type") or "").lower() != "exploit":
            continue
        refs = module.get("references") or []
        cve_ids = extract_cve_ids(*(str(ref) for ref in refs))
        if not cve_ids:
            continue
        fullname = (module.get("fullname") or "").strip()
        title = (module.get("name") or fullname or "Metasploit module").strip()
        published = (module.get("disclosure_date") or module.get("mod_time") or "")[:10]
        url = (
            f"https://www.rapid7.com/db/modules/{fullname}/"
            if fullname
            else "https://www.rapid7.com/db/"
        )
        card = exploit_card(
            title=title,
            exploit_type="metasploit",
            source=SOURCE_METASPLOIT,
            url=url,
            published_date=published,
        )
        for cve_id in cve_ids:
            mapping.setdefault(cve_id, []).append(card)
    return mapping


async def fetch_metasploit_metadata() -> dict | None:
    try:
        response = await resilient_get(
            "metasploit",
            METASPLOIT_METADATA_URL,
            timeout=180.0,
            queue_operation="exploit_feed_sync",
            queue_context_type="task",
            queue_context_id="metasploit_sync",
        )
        await record_api_call("metasploit", 1)
        return response.json()
    except CircuitOpenError:
        logger.warning("Metasploit circuit open — skipping metadata download")
        return None
    except httpx.HTTPError as exc:
        logger.error("Metasploit metadata download failed: %s", exc)
        return None
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Metasploit metadata parse failed: %s", exc)
        return None


async def sync_metasploit(db, known_cve_ids: set[str]) -> dict[str, int]:
    stats = {"cves": 0, "rows": 0, "skipped": 0}
    if os.environ.get("METASPLOIT_SYNC_ENABLED", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        stats["skipped"] = 1
        return stats

    payload = await fetch_metasploit_metadata()
    if not payload:
        return stats

    parsed = parse_metasploit_metadata(payload)
    filtered = {
        cve_id: cards
        for cve_id, cards in parsed.items()
        if cve_id in known_cve_ids
    }
    rows, cves = await replace_cve_exploits_by_source(db, SOURCE_METASPLOIT, filtered)
    stats["rows"] = rows
    stats["cves"] = cves
    stats["touched"] = sorted(filtered.keys())
    return stats
