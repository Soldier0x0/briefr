"""ThreatFox IOC mirror — thin delegate onto the unified ti_mirror store."""

from __future__ import annotations

from db.ti_mirror import upsert_ti_mirror_iocs
from db.types import DbConnection

_SOURCE = "threatfox"


async def upsert_threatfox_iocs(db: DbConnection, rows: list[dict]) -> int:
    """Insert or refresh ThreatFox rows in the unified mirror. Returns rows written."""
    return await upsert_ti_mirror_iocs(db, _SOURCE, rows)
