"""RB-1: resource utilization telemetry samples.

Revision ID: 023_resource_metrics
"""

from __future__ import annotations

from alembic import op

revision = "023_resource_metrics"
down_revision = "022_idx_cves_modified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_metrics (
            ts TEXT PRIMARY KEY,
            briefr_cpu_pct DOUBLE PRECISION,
            briefr_rss_bytes BIGINT,
            briefr_io_read_bps DOUBLE PRECISION,
            briefr_io_write_bps DOUBLE PRECISION,
            briefr_iops_r DOUBLE PRECISION,
            briefr_iops_w DOUBLE PRECISION,
            pg_cpu_pct DOUBLE PRECISION,
            pg_rss_bytes BIGINT,
            pg_iops_r DOUBLE PRECISION,
            pg_iops_w DOUBLE PRECISION,
            req_count INTEGER,
            pg_xact_per_min DOUBLE PRECISION,
            pg_blks_read_per_min DOUBLE PRECISION,
            pg_cache_hit_pct DOUBLE PRECISION,
            pg_db_size_bytes BIGINT,
            disk_free_bytes BIGINT,
            sys_cpu_pct DOUBLE PRECISION,
            sys_mem_pct DOUBLE PRECISION
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_resource_metrics_ts ON resource_metrics(ts)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_resource_metrics_ts")
    op.execute("DROP TABLE IF EXISTS resource_metrics")
