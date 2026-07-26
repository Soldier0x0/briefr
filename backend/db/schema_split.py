"""sync_state routing helpers for intel/app schema split."""

from __future__ import annotations

from db.schema_inventory import SYNC_STATE_INGEST_KEYS


async def schemas_are_split(conn) -> bool:
    """Return True when ``intel`` schema exists and holds ``cves``."""
    rows = await conn.execute_fetchall(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'intel' AND table_name = 'cves'
        LIMIT 1
        """
    )
    return bool(rows)


def sync_state_table(key: str, *, split: bool) -> str:
    if not split:
        return "sync_state"
    if key in SYNC_STATE_INGEST_KEYS:
        return "intel.sync_state"
    return "app.sync_state"
