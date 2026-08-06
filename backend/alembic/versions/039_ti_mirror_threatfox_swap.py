"""ThreatFox migration onto the unified ti_mirror store (multi-source corroboration).

The physical app.threatfox_iocs table is backfilled into app.ti_mirror_iocs
(source='threatfox'), then dropped and replaced by a compat view of the same
name so existing readers (retro_match.py, threatfox corroboration) keep
working unchanged. Writes move to ti_mirror_iocs via db/threatfox.py.

Revision ID: 039_ti_mirror_threatfox_swap
Revises: 038_ti_mirror_iocs
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "039_ti_mirror_threatfox_swap"
down_revision = "038_ti_mirror_iocs"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"

# Frozen at migration write-time: domain rows mirror the canonical value; URL
# rows (should not occur — the ThreatFox feed always maps URL -> domain host)
# would carry their hostname. Matches 037's _legacy_host semantics.
_BACKFILL_HOST_IOC = """
    CASE
        WHEN UPPER(t.ioc_type) IN ('DOMAIN', 'HOSTNAME')
            THEN RTRIM(LOWER(t.ioc_value), '.')
        WHEN UPPER(t.ioc_type) IN ('URL', 'URI')
            THEN RTRIM(
                LOWER(SPLIT_PART(SPLIT_PART(t.ioc_value, '://', 2), '/', 1)),
                '.'
            )
        ELSE ''
    END
"""


def upgrade() -> None:
    # Alembic runs without the app pool's search_path, so qualify explicitly.
    op.execute(
        f"""
        INSERT INTO app.ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc,
            malware, threat_type, confidence_level, first_seen, fetched_at
        )
        SELECT
            'threatfox',
            t.ioc_id,
            t.ioc_type,
            t.ioc_value,
            t.raw_ioc,
            {_BACKFILL_HOST_IOC},
            t.malware,
            t.threat_type,
            t.confidence_level,
            t.first_seen,
            t.fetched_at
        FROM app.threatfox_iocs t
        ON CONFLICT (source, ref_id) DO NOTHING
        """
    )
    op.execute("DROP TABLE IF EXISTS app.threatfox_iocs")
    op.execute(
        """
        CREATE VIEW app.threatfox_iocs AS
        SELECT ref_id AS ioc_id,
               ioc_type,
               ioc_value,
               raw_ioc,
               malware,
               threat_type,
               confidence_level,
               first_seen,
               fetched_at
        FROM app.ti_mirror_iocs
        WHERE source = 'threatfox'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS app.threatfox_iocs")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS app.threatfox_iocs (
            ioc_id TEXT PRIMARY KEY,
            ioc_type TEXT NOT NULL,
            ioc_value TEXT NOT NULL,
            raw_ioc TEXT NOT NULL DEFAULT '',
            malware TEXT NOT NULL DEFAULT '',
            threat_type TEXT NOT NULL DEFAULT '',
            confidence_level INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT NOT NULL DEFAULT '',
            fetched_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_value "
        "ON app.threatfox_iocs (ioc_value)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_type_value "
        "ON app.threatfox_iocs (ioc_type, ioc_value)"
    )
    op.execute(
        """
        INSERT INTO app.threatfox_iocs (
            ioc_id, ioc_type, ioc_value, raw_ioc,
            malware, threat_type, confidence_level, first_seen, fetched_at
        )
        SELECT ref_id, ioc_type, ioc_value, raw_ioc,
               malware, threat_type, confidence_level, first_seen, fetched_at
        FROM app.ti_mirror_iocs
        WHERE source = 'threatfox'
        ON CONFLICT (ioc_id) DO NOTHING
        """
    )
