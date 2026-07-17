"""stack_backfill_runs + checkpoints (Q4 Tier A).

Revision ID: 031_stack_backfill
Revises: 030_software_catalog
Create Date: 2026-07-17
"""

from __future__ import annotations

from alembic import op

revision = "031_stack_backfill"
down_revision = "030_software_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stack_backfill_runs (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            products_json TEXT NOT NULL DEFAULT '[]',
            max_products INTEGER NOT NULL DEFAULT 10,
            max_cves INTEGER NOT NULL DEFAULT 5000,
            max_runtime_seconds INTEGER NOT NULL DEFAULT 3600,
            eta_low_seconds INTEGER,
            eta_high_seconds INTEGER,
            cves_upserted INTEGER NOT NULL DEFAULT 0,
            pages_done INTEGER NOT NULL DEFAULT 0,
            pages_total INTEGER NOT NULL DEFAULT 0,
            progress_message TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_stack_backfill_runs_user "
        "ON stack_backfill_runs (user_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stack_backfill_checkpoints (
            id BIGSERIAL PRIMARY KEY,
            run_id BIGINT NOT NULL REFERENCES stack_backfill_runs(id) ON DELETE CASCADE,
            product_key TEXT NOT NULL,
            vendor TEXT,
            product TEXT NOT NULL,
            version TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            start_index INTEGER NOT NULL DEFAULT 0,
            total_results INTEGER NOT NULL DEFAULT 0,
            cves_upserted INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (run_id, product_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_stack_backfill_checkpoints_run "
        "ON stack_backfill_checkpoints (run_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stack_backfill_checkpoints")
    op.execute("DROP TABLE IF EXISTS stack_backfill_runs")
