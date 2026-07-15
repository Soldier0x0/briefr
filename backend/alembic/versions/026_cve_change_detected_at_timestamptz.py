"""PM-0e: cve_change_history.detected_at TEXT → TIMESTAMPTZ (Postgres).

SQLite test/dev fallback keeps TEXT via db/init.py — this migration is
Postgres-only (Alembic production path).

Revision ID: 026_cve_change_detected_at_timestamptz
"""

from __future__ import annotations

from alembic import op

revision = "026_cve_change_detected_at_timestamptz"
down_revision = "025_correlation_cve_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at TYPE TIMESTAMPTZ
        USING NULLIF(TRIM(detected_at), '')::timestamptz
        """
    )
    op.execute(
        """
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at SET DEFAULT (timezone('utc', now()))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at DROP DEFAULT
        """
    )
    op.execute(
        """
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at TYPE TEXT
        USING to_char(
            detected_at AT TIME ZONE 'UTC',
            'YYYY-MM-DD HH24:MI:SS'
        )
        """
    )
