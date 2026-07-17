"""software_catalog for NVD CPE dictionary (Q3).

Revision ID: 030_software_catalog
Revises: 029_api_call_events
Create Date: 2026-07-17
"""

from __future__ import annotations

from alembic import op

revision = "030_software_catalog"
down_revision = "029_api_call_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS software_catalog (
            cpe_uri TEXT PRIMARY KEY,
            vendor TEXT NOT NULL,
            product TEXT NOT NULL,
            version TEXT,
            display_name TEXT,
            category TEXT NOT NULL DEFAULT 'other',
            title TEXT,
            versions_json TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_software_catalog_product "
        "ON software_catalog (product)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_software_catalog_vendor_product "
        "ON software_catalog (vendor, product)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_software_catalog_display_trgm "
        "ON software_catalog USING gin (display_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_software_catalog_product_trgm "
        "ON software_catalog USING gin (product gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_software_catalog_product_trgm")
    op.execute("DROP INDEX IF EXISTS idx_software_catalog_display_trgm")
    op.execute("DROP INDEX IF EXISTS idx_software_catalog_vendor_product")
    op.execute("DROP INDEX IF EXISTS idx_software_catalog_product")
    op.execute("DROP TABLE IF EXISTS software_catalog")
