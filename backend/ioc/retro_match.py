"""Local IOC watchlist retro-match (V1.5 Theme 4b).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

from database import get_db
from db.types import DbConnection

logger = logging.getLogger(__name__)

_RETRO_MATCH_SQL_PG = """
    SELECT w.id AS watchlist_id, w.user_id, w.ioc_type, w.ioc_value, w.label,
           'otx' AS source, o.pulse_id AS ref_id,
           COALESCE(o.description, '') AS detail,
           camp.campaign_id,
           camp.label AS campaign_label,
           camp.lifecycle AS campaign_lifecycle,
           camp.confidence AS campaign_confidence,
           camp.member_count AS campaign_member_count,
           NULL AS mirror_confidence,
           NULL AS mirror_malware,
           NULL AS mirror_threat_type,
           NULL AS mirror_first_seen
    FROM ioc_watchlist w
    INNER JOIN otx_pulse_iocs o
        ON o.ioc_type = UPPER(w.ioc_type)
        AND (
            o.ioc_value_digest = md5(trim(w.ioc_value))
            OR LOWER(o.ioc_value) = LOWER(w.ioc_value)
        )
    LEFT JOIN correlation_campaigns camp
        ON camp.primary_pulse_id = o.pulse_id
    UNION ALL
    SELECT w.id, w.user_id, w.ioc_type, w.ioc_value, w.label,
           m.source AS source, m.ref_id AS ref_id,
           COALESCE(m.malware, m.threat_type, '') AS detail,
           NULL, NULL, NULL, NULL, NULL,
           m.confidence_level AS mirror_confidence,
           m.malware AS mirror_malware,
           m.threat_type AS mirror_threat_type,
           m.first_seen AS mirror_first_seen
    FROM ioc_watchlist w
    INNER JOIN ti_mirror_iocs m
        ON (
            (m.ioc_type = w.ioc_type AND (
                m.ioc_value_digest = md5(trim(w.ioc_value))
                OR LOWER(m.ioc_value) = LOWER(w.ioc_value)
            ))
            OR (m.ioc_type = 'url' AND UPPER(w.ioc_type) IN ('DOMAIN', 'URL')
                AND m.host_ioc != '' AND LOWER(m.host_ioc) = LOWER(w.ioc_value))
        )
"""

_RETRO_MATCH_SQL_SQLITE = """
    SELECT w.id AS watchlist_id, w.user_id, w.ioc_type, w.ioc_value, w.label,
           'otx' AS source, o.pulse_id AS ref_id,
           COALESCE(o.description, '') AS detail,
           camp.campaign_id,
           camp.label AS campaign_label,
           camp.lifecycle AS campaign_lifecycle,
           camp.confidence AS campaign_confidence,
           camp.member_count AS campaign_member_count,
           NULL AS mirror_confidence,
           NULL AS mirror_malware,
           NULL AS mirror_threat_type,
           NULL AS mirror_first_seen
    FROM ioc_watchlist w
    INNER JOIN otx_pulse_iocs o
        ON o.ioc_type = UPPER(w.ioc_type)
        AND LOWER(o.ioc_value) = LOWER(w.ioc_value)
    LEFT JOIN correlation_campaigns camp
        ON camp.primary_pulse_id = o.pulse_id
    UNION ALL
    SELECT w.id, w.user_id, w.ioc_type, w.ioc_value, w.label,
           m.source AS source, m.ref_id AS ref_id,
           COALESCE(m.malware, m.threat_type, '') AS detail,
           NULL, NULL, NULL, NULL, NULL,
           m.confidence_level AS mirror_confidence,
           m.malware AS mirror_malware,
           m.threat_type AS mirror_threat_type,
           m.first_seen AS mirror_first_seen
    FROM ioc_watchlist w
    INNER JOIN ti_mirror_iocs m
        ON (
            (m.ioc_type = w.ioc_type AND LOWER(m.ioc_value) = LOWER(w.ioc_value))
            OR (m.ioc_type = 'url' AND UPPER(w.ioc_type) IN ('DOMAIN', 'URL')
                AND m.host_ioc != '' AND LOWER(m.host_ioc) = LOWER(w.ioc_value))
        )
"""


def _retro_match_sql(db: DbConnection) -> str:
    if type(db).__name__ == "PostgresConnection":
        return _RETRO_MATCH_SQL_PG
    return _RETRO_MATCH_SQL_SQLITE


async def find_retro_matches(db: DbConnection) -> list[dict[str, Any]]:
    """Join saved IOC watchlist entries against local OTX + catalog mirrors."""
    rows = await db.execute_fetchall(_retro_match_sql(db))
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
