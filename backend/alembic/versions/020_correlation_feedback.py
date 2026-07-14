"""CORR-PR-12: analyst correlation feedback.

Revision ID: 020_correlation_feedback
"""

from __future__ import annotations

from alembic import op

revision = "020_correlation_feedback"
down_revision = "019_pulse_families"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS correlation_feedback (
            id SERIAL PRIMARY KEY,
            cve_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            verdict TEXT NOT NULL,
            reason TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_correlation_feedback_unique
            ON correlation_feedback(cve_id, scope, scope_key, verdict)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_feedback_cve ON correlation_feedback(cve_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_correlation_feedback_cve")
    op.execute("DROP INDEX IF EXISTS idx_correlation_feedback_unique")
    op.execute("DROP TABLE IF EXISTS correlation_feedback")
