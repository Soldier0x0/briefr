"""Widen alembic_version.version_num — default VARCHAR(32) is too short for descriptive IDs.

Revision ID: 027_alembic_version_num_widen
"""

from __future__ import annotations

from alembic import op

revision = "027_alembic_version_num_widen"
down_revision = "026_cve_detected_at_tz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(128)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(32)
        """
    )
