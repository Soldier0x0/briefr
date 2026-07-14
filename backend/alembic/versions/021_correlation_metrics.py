"""CORR-PR-13: nightly correlation quality metrics snapshot.

Revision ID: 021_correlation_metrics
"""

from __future__ import annotations

from alembic import op

revision = "021_correlation_metrics"
down_revision = "020_correlation_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS correlation_metrics (
            day TEXT PRIMARY KEY,
            computed_at TEXT,
            suppressions_30d INTEGER NOT NULL DEFAULT 0,
            feedback_confirm_30d INTEGER NOT NULL DEFAULT 0,
            feedback_reject_30d INTEGER NOT NULL DEFAULT 0,
            surfaced_findings_30d INTEGER NOT NULL DEFAULT 0,
            rejection_rate REAL,
            confirmation_rate REAL,
            weak_edge_ratio REAL,
            hub_suppressed_edge_count INTEGER NOT NULL DEFAULT 0,
            ioc_degree_p95 INTEGER NOT NULL DEFAULT 0,
            avg_independent_sources REAL,
            orphan_cve_ratio REAL,
            campaigns_active INTEGER NOT NULL DEFAULT 0,
            campaigns_retracted INTEGER NOT NULL DEFAULT 0,
            campaign_survival_rate REAL,
            campaign_member_count INTEGER NOT NULL DEFAULT 0,
            stale_campaign_ratio REAL,
            median_evidence_age_days REAL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS correlation_metrics")
