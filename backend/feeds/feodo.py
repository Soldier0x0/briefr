"""Feodo Tracker botnet C2 IP blocklist ingest (abuse.ch, CC0).

Public CSV — no Auth-Key required. Rows are stored in ti_mirror_iocs as
ioc_type='ip' for correlation and watchlist matching (not blocklist export).
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

FEODO_IPBLOCKLIST_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.csv"


def parse_feodo_row(row: dict[str, Any]) -> dict[str, str] | None:
    """Map one Feodo CSV row onto a ti_mirror row (IP IOC)."""
    ip = (row.get("dst_ip") or "").strip().strip('"')
    if not ip:
        return None
    port = (row.get("dst_port") or "").strip().strip('"')
    ref_id = f"{ip}:{port}" if port else ip
    malware = (row.get("malware") or "").strip().strip('"')
    status = (row.get("c2_status") or "").strip().strip('"')
    return {
        "ioc_id": ref_id,
        "ioc_type": "ip",
        "ioc_value": ip,
        "raw_ioc": ref_id,
        "host_ioc": "",
        "malware": malware,
        "threat_type": status or "botnet_c2",
        "confidence_level": "100" if status == "online" else "80",
        "first_seen": (row.get("first_seen_utc") or "").strip().strip('"'),
    }


def _parse_feodo_csv(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    parsed: list[dict[str, str]] = []
    for row in reader:
        mapped = parse_feodo_row(row)
        if mapped:
            parsed.append(mapped)
    return parsed


async def fetch_feodo_iocs(_auth_key: str = "", *, days: int = 7) -> list[dict[str, str]]:
    """Fetch the public Feodo IP blocklist CSV.

    ``days`` is accepted for catalog-sync signature parity (Feodo publishes
    the current blocklist snapshot only).
    """
    del days  # snapshot feed — no lookback window
    try:
        response = await resilient_request(
            "feodo",
            "GET",
            FEODO_IPBLOCKLIST_URL,
            timeout=120.0,
            queue_operation="threat_intel_sync",
            queue_context_type="task",
            queue_context_id="feodo_sync",
        )
        await record_api_call("feodo", 1)
    except CircuitOpenError:
        logger.warning("Feodo circuit open — skipping sync")
        return []
    except Exception as exc:
        logger.error("Feodo fetch failed: %s", exc)
        return []

    if response.status_code != 200:
        logger.warning("Feodo HTTP %s", response.status_code)
        return []

    return _parse_feodo_csv(response.text)
