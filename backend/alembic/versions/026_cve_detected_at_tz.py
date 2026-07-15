"""PM-0e: cve_change_history.detected_at TEXT → TIMESTAMPTZ (Postgres).

SQLite test/dev fallback keeps TEXT via db/init.py — this migration is
Postgres-only (Alembic production path).

Revision ID: 026_cve_detected_at_tz (<=32 chars for alembic_version.version_num)
"""

from __future__ import annotations

from alembic import op

revision = "026_cve_detected_at_tz"
down_revision = "025_correlation_cve_snapshot"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    # Drop the TEXT default before TYPE change — Postgres cannot auto-cast
    # TO_CHAR(...) defaults to timestamptz (026 deploy failure on production).
    op.execute(
        """
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at DROP DEFAULT
        """
    )
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
    op.execute(
        f"""
        ALTER TABLE cve_change_history
        ALTER COLUMN detected_at SET DEFAULT ({_TS})
        """
    )
