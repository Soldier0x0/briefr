"""CORR-PR-6: observed_at on otx_pulse_iocs (Phase 2 temporal truth).

OTX indicator ``created`` is captured at ingest as ``observed_at``. Nullable,
no backfill — NULL rows fall back to ``fetched_at`` in later Phase 2 PRs.

Note: correlation-engine-v2.md §18 references this as migration 017 — that
number was taken by 017_ioc_degree.py (CORR-PR-3). This is 018.

Revision ID: 018_otx_pulse_iocs_observed_at
"""

from __future__ import annotations

from alembic import op

revision = "018_otx_pulse_iocs_observed_at"
down_revision = "017_ioc_degree"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE otx_pulse_iocs
        ADD COLUMN IF NOT EXISTS observed_at TEXT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE otx_pulse_iocs
        DROP COLUMN IF EXISTS observed_at
        """
    )
