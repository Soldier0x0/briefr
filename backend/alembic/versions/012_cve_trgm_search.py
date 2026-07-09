"""Add pg_trgm GIN indexes for CVE text search (Track I7).

Revision ID: 012_cve_trgm_search
"""

from __future__ import annotations

from alembic import op

revision = "012_cve_trgm_search"
down_revision = "011_ioc_watchlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cves_description_trgm
        ON cves USING gin (lower(description) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cves_summary_trgm
        ON cves USING gin (lower(summary) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cves_affected_products_trgm
        ON cves USING gin (lower(affected_products) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cves_affected_products_trgm")
    op.execute("DROP INDEX IF EXISTS idx_cves_summary_trgm")
    op.execute("DROP INDEX IF EXISTS idx_cves_description_trgm")
