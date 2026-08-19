"""PhishTank verified-online phishing URL ingest (permissive community license).

Public CSV; optional PHISHTANK_APP_KEY raises rate limits. Rows are stored as
ioc_type='url' (high-trust catalog evidence for blocklist export, same rail as
URLhaus).
"""

from __future__ import annotations

import csv
import io
import logging
import os
from typing import Any

from correlation.ioc_normalize import _url_host, normalize_ioc
from feeds.errors import FeedFetchError
from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

PHISHTANK_CSV_BASE = "https://data.phishtank.com/data"


def phishtank_csv_url(app_key: str = "") -> str:
    key = (app_key or os.environ.get("PHISHTANK_APP_KEY", "")).strip()
    if key:
        return f"{PHISHTANK_CSV_BASE}/{key}/online-valid.csv"
    return f"{PHISHTANK_CSV_BASE}/online-valid.csv"


def parse_phishtank_row(row: dict[str, Any]) -> dict[str, str] | None:
    """Map one PhishTank CSV row onto a ti_mirror URL row."""
    ref_id = str(row.get("phish_id") or "").strip()
    raw_url = (row.get("url") or "").strip()
    if not ref_id or not raw_url:
        return None
    if (row.get("verified") or "").strip().lower() not in ("yes", "y", "1", "true"):
        return None
    if (row.get("online") or "").strip().lower() not in ("yes", "y", "1", "true"):
        return None

    normalized = normalize_ioc("URL", raw_url)
    if normalized is None:
        return None
    _canon_type, canon_value, _meta = normalized
    host = _url_host(canon_value)
    if not host:
        return None

    target = (row.get("target") or "").strip()
    return {
        "ioc_id": ref_id,
        "ioc_type": "url",
        "ioc_value": canon_value,
        "raw_ioc": raw_url,
        "host_ioc": host,
        "malware": "",
        "threat_type": f"phishing:{target}" if target else "phishing",
        "confidence_level": "100",
        "first_seen": (row.get("verification_time") or row.get("submission_time") or "").strip(),
    }


def _parse_phishtank_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    parsed: list[dict[str, str]] = []
    for row in reader:
        mapped = parse_phishtank_row(row)
        if mapped:
            parsed.append(mapped)
    return parsed


async def fetch_phishtank_iocs(auth_key: str = "", *, days: int = 7) -> list[dict[str, str]]:
    """Fetch PhishTank verified-online CSV (rolling snapshot).

    ``days`` is accepted for catalog-sync signature parity (no upstream window).
    """
    del days
    url = phishtank_csv_url(auth_key)
    try:
        response = await resilient_request(
            "phishtank",
            "GET",
            url,
            timeout=180.0,
            queue_operation="threat_intel_sync",
            queue_context_type="task",
            queue_context_id="phishtank_sync",
        )
        await record_api_call("phishtank", 1)
    except CircuitOpenError as exc:
        logger.warning("PhishTank circuit open — sync failed")
        raise FeedFetchError("PhishTank circuit open") from exc
    except Exception as exc:
        logger.error("PhishTank fetch failed: %s", exc)
        raise FeedFetchError("PhishTank request failed") from exc

    if response.status_code != 200:
        logger.warning("PhishTank HTTP %s", response.status_code)
        raise FeedFetchError(f"PhishTank HTTP {response.status_code}")

    return _parse_phishtank_csv(response.text)
