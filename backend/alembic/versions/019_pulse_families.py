"""CORR-PR-9: pulse families + campaign family metadata (Phase 3).

Revision ID: 019_pulse_families
"""

from __future__ import annotations

from alembic import op

revision = "019_pulse_families"
down_revision = "018_otx_pulse_iocs_observed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pulse_families (
            pulse_id TEXT PRIMARY KEY,
            family_id TEXT NOT NULL,
            jaccard REAL,
            computed_at TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pulse_families_family ON pulse_families(family_id)"
    )
    for col, typedef in (
        ("family_id", "TEXT"),
        ("first_seen", "TEXT"),
        ("last_seen", "TEXT"),
        ("independent_sources", "INTEGER DEFAULT 1"),
        ("author_count", "INTEGER DEFAULT 1"),
        ("retracted_at", "TEXT"),
    ):
        op.execute(
            f"""
            ALTER TABLE correlation_campaigns
            ADD COLUMN IF NOT EXISTS {col} {typedef}
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pulse_families_family")
    op.execute("DROP TABLE IF EXISTS pulse_families")
    for col in (
        "retracted_at",
        "author_count",
        "independent_sources",
        "last_seen",
        "first_seen",
        "family_id",
    ):
        op.execute(f"ALTER TABLE correlation_campaigns DROP COLUMN IF EXISTS {col}")
