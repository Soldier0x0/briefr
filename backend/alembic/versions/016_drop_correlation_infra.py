"""Drop dead correlation_infrastructure table (D8) + composite IOC index note.

No correlation code writes this table (find_shared_infrastructure_v2 reads
otx_pulse_iocs directly, not this table). idx_otx_pulse_iocs_type_value
already exists (added in 004_sqlite_schema_parity) — D10 was already fixed,
no action needed here.

Revision ID: 016_drop_correlation_infra
"""

from __future__ import annotations

from alembic import op

revision = "016_drop_correlation_infra"
down_revision = "015_user_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_correlation_infra_a")
    op.execute("DROP INDEX IF EXISTS idx_correlation_infra_b")
    op.execute("DROP TABLE IF EXISTS correlation_infrastructure")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS correlation_infrastructure (
            cve_id_a TEXT NOT NULL,
            cve_id_b TEXT NOT NULL,
            shared_ip_count INTEGER DEFAULT 0,
            confidence TEXT DEFAULT 'low',
            detected_at TEXT DEFAULT (timezone('utc', now())::text),
            PRIMARY KEY (cve_id_a, cve_id_b)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_infra_a "
        "ON correlation_infrastructure(cve_id_a)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_correlation_infra_b "
        "ON correlation_infrastructure(cve_id_b)"
    )
