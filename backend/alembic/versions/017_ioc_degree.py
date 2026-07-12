"""CORR-PR-3: ioc_degree table for degree-penalized edge confidence.

Note: correlation-engine-v2.md spec §14/§18 references this as migration
016 -- that number was taken by 016_drop_correlation_infra.py (CORR-PR-2,
merged first). This is 017; the spec's number is stale, not a conflict.

One row per (ioc_type, ioc_value) tracking how many distinct CVEs and OTX
pulses reference it. Rebuilt nightly via a single truncate-and-INSERT...SELECT
(db/correlation.py::rebuild_ioc_degree) -- a plain table, not a materialized
view, so it's SQLite-testable and refresh-lock-free (spec §19).

Revision ID: 017_ioc_degree
"""

from __future__ import annotations

from alembic import op

revision = "017_ioc_degree"
down_revision = "016_drop_correlation_infra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ioc_degree (
            ioc_type TEXT NOT NULL,
            ioc_value TEXT NOT NULL,
            cve_count INTEGER NOT NULL DEFAULT 0,
            pulse_count INTEGER NOT NULL DEFAULT 0,
            computed_at TEXT DEFAULT (timezone('utc', now())::text),
            PRIMARY KEY (ioc_type, ioc_value)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ioc_degree")
