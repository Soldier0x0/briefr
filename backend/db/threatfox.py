"""ThreatFox IOC mirror table (V1.5 Theme 4b)."""

from __future__ import annotations

from db.timeutil import utcnow_str
from db.types import DbConnection


async def upsert_threatfox_iocs(db: DbConnection, rows: list[dict]) -> int:
    """Insert or refresh ThreatFox rows. Returns rows written."""
    if not rows:
        return 0
    now = utcnow_str()
    written = 0
    for row in rows:
        await db.execute(
            """
            INSERT INTO threatfox_iocs (
                ioc_id, ioc_type, ioc_value, raw_ioc, malware,
                threat_type, confidence_level, first_seen, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ioc_id) DO UPDATE SET
                ioc_type = excluded.ioc_type,
                ioc_value = excluded.ioc_value,
                raw_ioc = excluded.raw_ioc,
                malware = excluded.malware,
                threat_type = excluded.threat_type,
                confidence_level = excluded.confidence_level,
                first_seen = excluded.first_seen,
                fetched_at = excluded.fetched_at
            """,
            (
                row["ioc_id"],
                row["ioc_type"],
                row["ioc_value"],
                row.get("raw_ioc") or row["ioc_value"],
                row.get("malware") or "",
                row.get("threat_type") or "",
                int(row.get("confidence_level") or 0),
                row.get("first_seen") or "",
                now,
            ),
        )
        written += 1
    return written
