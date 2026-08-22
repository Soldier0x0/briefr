"""Unified TI mirror store (ti_mirror_iocs) shared by all catalog sources."""

from __future__ import annotations

from db.ioc_digest import ioc_value_digest
from db.timeutil import utcnow_str
from db.types import DbConnection


async def upsert_ti_mirror_iocs(
    db: DbConnection, source: str, rows: list[dict]
) -> int:
    """Insert or refresh mirror rows for one source. Returns rows written.

    Rows use the mirror column names (`ref_id`, `host_ioc`, …); `ioc_id` is
    accepted as an alias for `ref_id` to keep legacy fetch callers working.
    """
    if not rows:
        return 0
    now = utcnow_str()
    written = 0
    for row in rows:
        ref_id = row.get("ref_id") or row.get("ioc_id")
        if not ref_id:
            continue
        ioc_value = row.get("ioc_value") or ""
        await db.execute(
            """
            INSERT INTO ti_mirror_iocs (
                source, ref_id, ioc_type, ioc_value, ioc_value_digest, raw_ioc,
                host_ioc, malware, threat_type, confidence_level, first_seen,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, ref_id) DO UPDATE SET
                ioc_type = excluded.ioc_type,
                ioc_value = excluded.ioc_value,
                ioc_value_digest = excluded.ioc_value_digest,
                raw_ioc = excluded.raw_ioc,
                host_ioc = excluded.host_ioc,
                malware = excluded.malware,
                threat_type = excluded.threat_type,
                confidence_level = excluded.confidence_level,
                first_seen = excluded.first_seen,
                fetched_at = excluded.fetched_at
            """,
            (
                source,
                ref_id,
                row.get("ioc_type") or "",
                ioc_value,
                ioc_value_digest(ioc_value),
                row.get("raw_ioc") or ioc_value,
                row.get("host_ioc") or "",
                row.get("malware") or "",
                row.get("threat_type") or "",
                int(row.get("confidence_level") or 0),
                row.get("first_seen") or "",
                now,
            ),
        )
        written += 1
    return written
