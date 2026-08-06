"""Unified catalog-mirror table ti_mirror_iocs (multi-source TI corroboration).

Phase 0 of the multi-source corroboration plan: a single app-schema mirror
table for bulk catalog IOC sources (ThreatFox migrated first, then URLhaus,
MalwareBazaar, …). One table, one registry-driven upsert, one corroboration
join path.

Revision ID: 038_ti_mirror_iocs
Revises: 037_otx_pulse_iocs_raw_host
"""

from __future__ import annotations

from alembic import op

revision = "038_ti_mirror_iocs"
down_revision = "037_otx_pulse_iocs_raw_host"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    # Alembic runs without the app pool's search_path, so qualify explicitly.
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS app.ti_mirror_iocs (
            source           TEXT NOT NULL,
            ref_id           TEXT NOT NULL,
            ioc_type         TEXT NOT NULL,
            ioc_value        TEXT NOT NULL,
            raw_ioc          TEXT DEFAULT '',
            host_ioc         TEXT DEFAULT '',
            malware          TEXT DEFAULT '',
            threat_type      TEXT DEFAULT '',
            confidence_level INTEGER DEFAULT 0,
            first_seen       TEXT DEFAULT '',
            fetched_at       TEXT DEFAULT ({_TS}),
            PRIMARY KEY (source, ref_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ti_mirror_type_value "
        "ON app.ti_mirror_iocs (ioc_type, ioc_value)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ti_mirror_host "
        "ON app.ti_mirror_iocs (host_ioc)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ti_mirror_source "
        "ON app.ti_mirror_iocs (source)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.ti_mirror_iocs")
