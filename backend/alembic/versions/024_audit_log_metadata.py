"""UX audit item 29: optional structured context on audit_log rows.

Revision ID: 024_audit_log_metadata
"""

from __future__ import annotations

from alembic import op

revision = "024_audit_log_metadata"
down_revision = "023_resource_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS metadata_json TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS metadata_json")
