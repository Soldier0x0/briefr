"""URLhaus bulk URL catalog ingest (abuse.ch Auth-Key)."""

from __future__ import annotations

import logging
from typing import Any

from correlation.ioc_normalize import _url_host, normalize_ioc
from feeds.errors import FeedFetchError
from feeds.extended import abusech_headers
from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

URLHAUS_RECENT_API = "https://urlhaus-api.abuse.ch/v1/urls/recent/"


def _tag_list(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def parse_urlhaus_entry(entry: dict[str, Any]) -> dict[str, str] | None:
    """Map one URLhaus recent-URLs entry onto a ti_mirror row.

    Keeps the full canonical URL in ``ioc_value`` (no ingest-time downcast)
    and the derived host/domain in ``host_ioc`` so corroboration can join URL
    rows to DOMAIN edges via host and to URL edges via the verbatim value.
    """
    ref_id = str(entry.get("id") or "").strip()
    raw_url = (entry.get("url") or "").strip()
    if not ref_id or not raw_url:
        return None

    normalized = normalize_ioc("URL", raw_url)
    if normalized is None:
        return None
    _canon_type, canon_value, _meta = normalized
    host = _url_host(canon_value)
    if not host:
        return None

    threat = (entry.get("threat") or entry.get("threat_type") or "").strip()
    return {
        "ioc_id": ref_id,
        "ioc_type": "url",
        "ioc_value": canon_value,
        "raw_ioc": raw_url,
        "host_ioc": host,
        "malware": ", ".join(_tag_list(entry.get("tags"))),
        "threat_type": threat,
        "confidence_level": "100",
        "first_seen": (entry.get("date_added") or "").strip(),
    }


async def fetch_urlhaus_iocs(auth_key: str, *, days: int = 7) -> list[dict[str, str]]:
    """Fetch recent URLhaus entries (max 1000 per the API).

    ``days`` (keep for catalog-sync signature parity) is a no-op upstream: the
    recent-URLs endpoint returns a rolling ~3-day window regardless. The
    ``URLHAUS_SYNC_DAYS`` env only signals intent; it cannot widen the fetch.
    """
    key = (auth_key or "").strip()
    if not key:
        return []

    headers = abusech_headers(key)
    try:
        response = await resilient_request(
            "urlhaus",
            "GET",
            URLHAUS_RECENT_API,
            headers=headers,
            timeout=60.0,
            queue_operation="threat_intel_sync",
            queue_context_type="task",
            queue_context_id="urlhaus_sync",
        )
        await record_api_call("urlhaus", 1)
    except CircuitOpenError as exc:
        logger.warning("URLhaus circuit open — sync failed")
        raise FeedFetchError("URLhaus circuit open") from exc
    except Exception as exc:
        logger.error("URLhaus fetch failed: %s", exc)
        raise FeedFetchError("URLhaus request failed") from exc

    if response.status_code != 200:
        logger.warning("URLhaus HTTP %s", response.status_code)
        raise FeedFetchError(f"URLhaus HTTP {response.status_code}")

    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        logger.warning("URLhaus returned non-JSON body: %s", exc)
        raise FeedFetchError("URLhaus non-JSON body") from exc
    if not isinstance(body, dict):
        logger.warning("URLhaus returned non-object body: %r", body)
        raise FeedFetchError("URLhaus non-object body")
    if body.get("query_status") != "ok":
        logger.warning("URLhaus query_status: %s", body.get("query_status"))
        raise FeedFetchError(f"URLhaus query_status: {body.get('query_status')}")

    urls = body.get("urls")
    if not isinstance(urls, list):
        raise FeedFetchError("URLhaus urls payload is not a list")

    parsed: list[dict[str, str]] = []
    for entry in urls:
        if not isinstance(entry, dict):
            continue
        row = parse_urlhaus_entry(entry)
        if row:
            parsed.append(row)
    return parsed
