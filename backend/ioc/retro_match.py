"""Local IOC watchlist retro-match (V1.5 Theme 4b).

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from database import get_db
from db.types import DbConnection

logger = logging.getLogger(__name__)


async def find_retro_matches(db: DbConnection) -> list[dict[str, Any]]:
    """Join saved IOC watchlist entries against local OTX + ThreatFox mirrors."""
    rows = await db.execute_fetchall(
        """
        SELECT w.id AS watchlist_id, w.user_id, w.ioc_type, w.ioc_value, w.label,
               'otx' AS source, o.pulse_id AS ref_id,
               COALESCE(o.description, '') AS detail
        FROM ioc_watchlist w
        INNER JOIN otx_pulse_iocs o
            ON LOWER(o.ioc_value) = LOWER(w.ioc_value)
        UNION ALL
        SELECT w.id, w.user_id, w.ioc_type, w.ioc_value, w.label,
               'threatfox' AS source, t.ioc_id AS ref_id,
               COALESCE(t.malware, t.threat_type, '') AS detail
        FROM ioc_watchlist w
        INNER JOIN threatfox_iocs t
            ON t.ioc_type = w.ioc_type AND LOWER(t.ioc_value) = LOWER(w.ioc_value)
        """
    )
    return [dict(row) for row in rows]


async def run_ioc_retro_match() -> list[dict[str, Any]]:
    db = await get_db()
    try:
        matches = await find_retro_matches(db)
        if matches:
            logger.info("IOC retro-match: %d hit(s)", len(matches))
        return matches
    finally:
        await db.close()
