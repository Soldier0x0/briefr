"""IOC watchlist + ThreatFox mirror (V1.5 Theme 4b).

Revision ID: 011_ioc_watchlist
"""

from __future__ import annotations

from alembic import op

revision = "011_ioc_watchlist"
down_revision = "010_detection_backlog"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ioc_watchlist (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ioc_type TEXT NOT NULL,
            ioc_value TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT ({_TS}),
            UNIQUE (user_id, ioc_type, ioc_value)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_value ON ioc_watchlist(ioc_value)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ioc_watchlist_user ON ioc_watchlist(user_id)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS threatfox_iocs (
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
    op.execute("CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_value ON threatfox_iocs(ioc_value)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_threatfox_iocs_type_value ON threatfox_iocs(ioc_type, ioc_value)"
    )

    op.execute("ALTER TABLE cves ADD COLUMN IF NOT EXISTS is_vulncheck_exploited INTEGER DEFAULT 0")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cves_vulncheck_exploited ON cves(is_vulncheck_exploited)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cves_vulncheck_exploited")
    op.execute("ALTER TABLE cves DROP COLUMN IF EXISTS is_vulncheck_exploited")
    op.execute("DROP TABLE IF EXISTS threatfox_iocs")
    op.execute("DROP TABLE IF EXISTS ioc_watchlist")
