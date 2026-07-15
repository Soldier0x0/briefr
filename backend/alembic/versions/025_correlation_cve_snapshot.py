"""ADR-004: precomputed per-CVE correlation snapshots (off request path).

Revision ID: 025_correlation_cve_snapshot
"""

from __future__ import annotations

from alembic import op

revision = "025_correlation_cve_snapshot"
down_revision = "024_audit_log_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS correlation_cve_snapshot (
            cve_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            engine_version TEXT NOT NULL DEFAULT '',
            computed_at TEXT NOT NULL,
            hub_edges_suppressed INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_correlation_cve_snapshot_computed
            ON correlation_cve_snapshot(computed_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS correlation_cve_snapshot")
