"""Tranco top-1M legitimate-domain bulk import into infra_classifications.

Downloads the daily Tranco list and inserts missing hosts as LEGITIMATE_DOMAIN
rows with provenance ``tranco:<list-date>``. Operator edits are never
overwritten (ON CONFLICT DO NOTHING). After a successful non-empty snapshot,
Tranco-provenance rows whose hosts dropped off the list are disabled.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import datetime, timezone

from blocklist.infra_seed import LEGITIMATE_DOMAIN
from blocklist.classify import canonical_host
from db.blocklist import (
    bulk_insert_infra_classifications,
    expire_superseded_tranco_hosts,
)
from db.timeutil import utcnow_str
from db.types import DbConnection
from feeds.errors import FeedFetchError
from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

TRANCO_DAILY_ZIP_URL = "https://tranco-list.eu/download/daily/top-1m.csv.zip"
TRANCO_CSV_NAME = "top-1m.csv"
TRANCO_BATCH_SIZE = 5000


def _list_date_from_zip(zf: zipfile.ZipFile) -> str:
    for name in zf.namelist():
        # top-1m.csv or YYYY-MM-DD.csv inside the archive
        base = name.rsplit("/", 1)[-1]
        if base.endswith(".csv") and len(base) >= 10:
            prefix = base.split(".", 1)[0]
            if len(prefix) == 10 and prefix[4] == "-" and prefix[7] == "-":
                return prefix
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def fetch_tranco_domains() -> tuple[str, list[str]]:
    """Return (list_date, canonical domains) from the daily Tranco ZIP."""
    try:
        response = await resilient_request(
            "tranco",
            "GET",
            TRANCO_DAILY_ZIP_URL,
            timeout=300.0,
            queue_operation="threat_intel_sync",
            queue_context_type="task",
            queue_context_id="tranco_infra_sync",
        )
        await record_api_call("tranco", 1)
    except CircuitOpenError:
        logger.warning("Tranco circuit open — skipping infra sync")
        return "", []
    except FeedFetchError:
        raise
    except Exception as exc:
        logger.error("Tranco download failed: %s", exc)
        raise FeedFetchError("Tranco request failed") from exc

    if response.status_code != 200:
        logger.warning("Tranco HTTP %s", response.status_code)
        raise FeedFetchError(f"Tranco HTTP {response.status_code}")

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        list_date = _list_date_from_zip(zf)
        csv_name = next(
            (n for n in zf.namelist() if n.endswith(TRANCO_CSV_NAME) or n.endswith(".csv")),
            TRANCO_CSV_NAME,
        )
        with zf.open(csv_name) as raw:
            text = raw.read().decode("utf-8", errors="replace")

    domains: list[str] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 2:
            continue
        host = canonical_host(row[1])
        if host and "." in host:
            domains.append(host)
    return list_date, domains


async def _apply_tranco_snapshot(db: DbConnection, list_date: str, domains: list[str]) -> int:
    provenance = f"tranco:{list_date or utcnow_str()[:10]}"
    inserted = await bulk_insert_infra_classifications(
        db,
        domains,
        classification=LEGITIMATE_DOMAIN,
        provenance=provenance,
        reason="",  # provenance carries list identity (~120 MB saved at 1M rows)
        batch_size=TRANCO_BATCH_SIZE,
    )
    expired = await expire_superseded_tranco_hosts(db, domains)
    logger.info(
        "Tranco infra sync complete list=%s inserted=%d expired=%d scanned=%d",
        list_date or "unknown",
        inserted,
        expired,
        len(domains),
    )
    return inserted


async def sync_tranco_infra_classifications(db: DbConnection) -> int:
    """Download Tranco, insert missing legitimate-domain rows, expire drop-offs.

    Empty / circuit-open fetches return 0 and do not expire. Operator-owned
    rows (provenance not ``tranco:…``) are never disabled.
    """
    list_date, domains = await fetch_tranco_domains()
    if not domains:
        return 0
    return await _apply_tranco_snapshot(db, list_date, domains)
