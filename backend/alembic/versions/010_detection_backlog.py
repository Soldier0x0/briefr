"""Detection backlog table (V1.5 Theme 3).

Revision ID: 010_detection_backlog
"""

from __future__ import annotations

from alembic import op

revision = "010_detection_backlog"
down_revision = "009_app_settings"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS detection_backlog (
            id SERIAL PRIMARY KEY,
            cve_id TEXT NOT NULL,
            technique_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT 'kev_gap',
            priority TEXT NOT NULL DEFAULT 'high',
            status TEXT NOT NULL DEFAULT 'open',
            stack_terms TEXT NOT NULL DEFAULT '',
            technique_name TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT ({_TS}),
            dismissed_at TEXT,
            UNIQUE (cve_id, technique_id, reason)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_detection_backlog_status ON detection_backlog(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_detection_backlog_cve ON detection_backlog(cve_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS detection_backlog")
