"""Evidence-first retrieval for the threat-intel blocklist export.

Retrieval only — classification, confidence, dedup, and serialization live in
`blocklist/`. Every query here reads `ti_mirror_iocs` (app) and
`otx_pulse_iocs` (intel) without ever modifying them: exact IOC evidence is
preserved by design.
"""

from __future__ import annotations

from typing import Any

from db.cve import _is_postgres_connection
from db.timeutil import utcnow_str
from db.types import DbConnection

# Catalog rows that can back a *domain candidate*. ThreatFox rows are stored
# as ioc_type='domain' (URLs are downcast at ingest, raw_ioc keeps the URL);
# URLhaus rows are ioc_type='url' with host_ioc. MalwareBazaar carries hashes
# only and yields no domains, so it is intentionally not selected.
_CATALOG_EVIDENCE_SQLITE = """
SELECT source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
       threat_type, confidence_level, first_seen, fetched_at
FROM ti_mirror_iocs
WHERE source IN ('threatfox', 'urlhaus')
  AND ioc_type IN ('domain', 'url')
ORDER BY source, ref_id, ioc_type, ioc_value, first_seen, fetched_at
"""

_CATALOG_EVIDENCE_PG = """
SELECT source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
       threat_type, confidence_level, first_seen, fetched_at
FROM app.ti_mirror_iocs
WHERE source IN ('threatfox', 'urlhaus')
  AND ioc_type IN ('domain', 'url')
ORDER BY source, ref_id, ioc_type, ioc_value, first_seen, fetched_at
"""

# OTX pulse IOCs that can back a domain candidate. OTX is only ever used as
# corroborating/community evidence — never as the sole reason to export (see
# blocklist/build.py). raw_ioc/host_ioc preserve the exact upstream values.
_OTX_CANDIDATE_SQLITE = """
SELECT pulse_id, ioc_type, ioc_value, raw_ioc, host_ioc, description,
       fetched_at, observed_at
FROM otx_pulse_iocs
WHERE UPPER(ioc_type) IN ('DOMAIN', 'HOSTNAME', 'URL')
ORDER BY pulse_id, ioc_type, ioc_value, observed_at, fetched_at
"""

_OTX_CANDIDATE_PG = """
SELECT pulse_id, ioc_type, ioc_value, raw_ioc, host_ioc, description,
       fetched_at, observed_at
FROM intel.otx_pulse_iocs
WHERE UPPER(ioc_type) IN ('DOMAIN', 'HOSTNAME', 'URL')
ORDER BY pulse_id, ioc_type, ioc_value, observed_at, fetched_at
"""

# pg-only: infra_classifications exists only in the Postgres app schema
# (Alembic 040) — no SQLite bootstrap exists for it, so there is no
# SQLite query variant here.
_CLASSIFICATIONS_PG = """
SELECT host, classification, enabled, provenance, reason, notes,
       created_at, updated_at
FROM app.infra_classifications
"""


async def fetch_catalog_evidence(db: DbConnection) -> list[dict[str, Any]]:
    """Return ThreatFox/URLhaus mirror rows that can back a domain candidate."""
    pg = _is_postgres_connection(db)
    rows = await db.execute_fetchall(
        _CATALOG_EVIDENCE_PG if pg else _CATALOG_EVIDENCE_SQLITE
    )
    return [dict(row) for row in rows]


async def fetch_otx_candidates(db: DbConnection) -> list[dict[str, Any]]:
    """Return OTX pulse IOCs that may corroborate a domain candidate."""
    pg = _is_postgres_connection(db)
    rows = await db.execute_fetchall(
        _OTX_CANDIDATE_PG if pg else _OTX_CANDIDATE_SQLITE
    )
    return [dict(row) for row in rows]


async def fetch_infra_classifications(db: DbConnection) -> list[dict[str, Any]]:
    """Return every infrastructure-classification row (enabled or not).

    The classification table is Postgres-only (app.infra_classifications),
    so this queries the qualified app schema directly.
    """
    rows = await db.execute_fetchall(_CLASSIFICATIONS_PG)
    return [dict(row) for row in rows]


async def insert_infra_classification(
    db: DbConnection,
    *,
    host: str,
    classification: str,
    enabled: int = 1,
    provenance: str = "",
    reason: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Insert one classification row; raises ValueError on duplicate host."""
    now = utcnow_str()
    # Fast path: a duplicate host is a domain-logic error, not a DB error, so
    # surface it before touching the write (keeps the failure deterministic).
    existing = await db.execute_fetchall(
        "SELECT host FROM app.infra_classifications WHERE host = ?", (host,)
    )
    if existing:
        raise ValueError(f"Host already classified: {host}")
    try:
        await db.execute(
            "INSERT INTO app.infra_classifications ("
            " host, classification, enabled, provenance, reason, notes,"
            " created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (host, classification, enabled, provenance, reason, notes, now, now),
        )
    except Exception as exc:  # concurrent duplicate (UNIQUE) or dialect error
        # On Postgres a failed statement aborts the whole transaction; roll
        # back before probing so the next statement is not rejected.
        try:
            await db.rollback()
        except Exception:
            pass
        existing = await db.execute_fetchall(
            "SELECT host FROM app.infra_classifications WHERE host = ?", (host,)
        )
        if existing:
            raise ValueError(f"Host already classified: {host}") from exc
        raise
    rows = await db.execute_fetchall(
        "SELECT id, host, classification, enabled, provenance, reason, notes,"
        " created_at, updated_at FROM app.infra_classifications WHERE host = ?",
        (host,),
    )
    return dict(rows[0]) if rows else {}


async def update_infra_classification(
    db: DbConnection,
    row_id: int,
    *,
    classification: str | None = None,
    enabled: int | None = None,
    provenance: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Update an existing classification row in place; returns the row or None."""
    existing = await db.execute_fetchall(
        "SELECT id FROM app.infra_classifications WHERE id = ?", (row_id,)
    )
    if not existing:
        return None
    now = utcnow_str()
    sets: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("classification", classification),
        ("enabled", enabled),
        ("provenance", provenance),
        ("reason", reason),
        ("notes", notes),
    ):
        if value is not None:
            sets.append(f"{column} = ?")
            params.append(value)
    params.append(now)
    params.append(row_id)
    if sets:
        await db.execute(
            f"UPDATE app.infra_classifications SET {', '.join(sets)}, updated_at = ?"
            " WHERE id = ?",
            tuple(params),
        )
    rows = await db.execute_fetchall(
        "SELECT id, host, classification, enabled, provenance, reason, notes,"
        " created_at, updated_at FROM app.infra_classifications WHERE id = ?",
        (row_id,),
    )
    return dict(rows[0]) if rows else None


async def delete_infra_classification(db: DbConnection, row_id: int) -> bool:
    cursor = await db.execute(
        "DELETE FROM app.infra_classifications WHERE id = ?", (row_id,)
    )
    return (getattr(cursor, "rowcount", 0) or 0) > 0
