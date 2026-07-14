"""PR-P3: index on cves.modified for brief/OTX priority queries (IDX-001).

Revision ID: 022_idx_cves_modified
"""

from __future__ import annotations

from alembic import op

revision = "022_idx_cves_modified"
down_revision = "021_correlation_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cves_modified ON cves(modified)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cves_modified")
