"""Add epss_percentile column to cves.

Revision ID: 005_epss_percentile
"""

from __future__ import annotations

from alembic import op

revision = "005_epss_percentile"
down_revision = "004_sqlite_schema_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cves
        ADD COLUMN IF NOT EXISTS epss_percentile DOUBLE PRECISION
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE cves DROP COLUMN IF EXISTS epss_percentile")
