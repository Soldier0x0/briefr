"""VulnCheck community KEV catalog sync (V1.5 Theme 4b)."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

VULNCHECK_KEV_URL = "https://api.vulncheck.com/v3/index/vulncheck-kev"
CVE_RE = re.compile(r"CVE-\d{4}-\d+", re.I)


def vulncheck_enabled() -> bool:
    return bool(os.environ.get("VULNCHECK_API_KEY", "").strip())


def _extract_cve_ids(entry: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for key in ("cve", "id"):
        val = entry.get(key)
        if isinstance(val, str):
            found.update(m.upper() for m in CVE_RE.findall(val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    found.update(m.upper() for m in CVE_RE.findall(item))
    for ref in entry.get("vulncheck_reported_exploitation") or []:
        if isinstance(ref, dict):
            for m in CVE_RE.findall(str(ref.get("url") or "")):
                found.add(m.upper())
    return sorted(found)


async def fetch_vulncheck_kev_cve_ids(api_key: str, *, limit: int = 5000) -> list[str]:
    """Paginate VulnCheck KEV index and return CVE IDs."""
    key = (api_key or "").strip()
    if not key:
        return []

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
    }
    cve_ids: set[str] = set()
    page = 1
    per_page = 100

    while page <= 50 and len(cve_ids) < limit:
        try:
            response = await resilient_get(
                "vulncheck",
                VULNCHECK_KEV_URL,
                headers=headers,
                params={"page": page, "limit": per_page},
                timeout=60.0,
                queue_operation="cve_ingest",
                queue_context_type="task",
                queue_context_id="vulncheck_sync",
            )
            await record_api_call("vulncheck", 1)
        except CircuitOpenError:
            logger.warning("VulnCheck circuit open — skipping sync")
            break
        except Exception as exc:
            logger.error("VulnCheck fetch failed: %s", exc)
            break

        if response.status_code != 200:
            logger.warning("VulnCheck HTTP %s on page %s", response.status_code, page)
            break

        body = response.json()
        data = body.get("data") or []
        if not data:
            break

        for entry in data:
            for cve_id in _extract_cve_ids(entry):
                cve_ids.add(cve_id)

        meta = body.get("_meta") or {}
        total_pages = int(meta.get("total_pages") or meta.get("totalPages") or 1)
        if page >= total_pages:
            break
        page += 1

    return sorted(cve_ids)[:limit]
