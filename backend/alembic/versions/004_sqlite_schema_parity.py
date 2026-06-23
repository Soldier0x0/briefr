"""SQLite schema parity — correlation v2, OTX pulses, webhooks.

Revision ID: 004_sqlite_schema_parity
"""

from __future__ import annotations

from alembic import op

revision = "004_sqlite_schema_parity"
down_revision = "003_users_email_to_username"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE otx_cve_pulses
        ADD COLUMN IF NOT EXISTS targeted_countries TEXT DEFAULT '[]'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_otx_cve_pulses_pulse ON otx_cve_pulses(pulse_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_type_value "
        "ON otx_pulse_iocs(ioc_type, ioc_value)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS otx_pulses (
            pulse_id TEXT PRIMARY KEY,
            pulse_name TEXT NOT NULL DEFAULT '',
            author TEXT DEFAULT '',
            created_date TEXT DEFAULT '',
            adversary TEXT DEFAULT '',
            malware_families TEXT DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            targeted_countries TEXT DEFAULT '[]',
            ioc_count INTEGER DEFAULT 0,
            fetched_at TEXT DEFAULT ({_TS})
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_campaigns (
            campaign_id TEXT PRIMARY KEY,
            primary_pulse_id TEXT,
            label TEXT NOT NULL DEFAULT '',
            adversary TEXT DEFAULT '',
            malware_families TEXT DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            targeted_countries TEXT DEFAULT '[]',
            confidence TEXT DEFAULT 'medium',
            member_count INTEGER DEFAULT 0,
            lifecycle TEXT DEFAULT 'active',
            campaign_version TEXT DEFAULT '',
            computed_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_campaigns_pulse "
        "ON correlation_campaigns(primary_pulse_id)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_campaign_members (
            campaign_id TEXT NOT NULL,
            cve_id TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            PRIMARY KEY (campaign_id, cve_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_campaign_members_cve "
        "ON correlation_campaign_members(cve_id)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS correlation_suppressions (
            id SERIAL PRIMARY KEY,
            cve_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            reason TEXT DEFAULT '',
            dismissed_by TEXT DEFAULT '',
            created_at TEXT DEFAULT ({_TS}),
            UNIQUE (cve_id, scope, scope_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_suppressions_cve "
        "ON correlation_suppressions(cve_id)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS webhook_destinations (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            event_types TEXT NOT NULL DEFAULT '[]',
            config_json TEXT NOT NULL DEFAULT '{{}}',
            source TEXT NOT NULL DEFAULT 'db',
            created_at TEXT DEFAULT ({_TS}),
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS webhook_delivery_log (
            id SERIAL PRIMARY KEY,
            destination_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            dedupe_key TEXT,
            status TEXT NOT NULL,
            error TEXT,
            attempted_at TEXT DEFAULT ({_TS})
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_dest "
        "ON webhook_delivery_log(destination_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_at "
        "ON webhook_delivery_log(attempted_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_event "
        "ON webhook_delivery_log(event_type)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_delivery_log")
    op.execute("DROP TABLE IF EXISTS webhook_destinations")
    op.execute("DROP TABLE IF EXISTS correlation_suppressions")
    op.execute("DROP TABLE IF EXISTS correlation_campaign_members")
    op.execute("DROP TABLE IF EXISTS correlation_campaigns")
    op.execute("DROP TABLE IF EXISTS otx_pulses")
