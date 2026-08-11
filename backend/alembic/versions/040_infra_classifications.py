"""Infrastructure classifications for the threat-intel blocklist export.

Operator-curated, DB-backed infrastructure classification (exact canonical
host) that controls host-level corroboration and blocklist export eligibility
for malicious-domain candidates. Exact IOC evidence in ti_mirror_iocs /
otx_pulse_iocs is never deleted or rewritten by this feature.

Revision ID: 040_infra_classifications
Revises: 039_ti_mirror_threatfox_swap
"""

from __future__ import annotations

from alembic import op

revision = "040_infra_classifications"
down_revision = "039_ti_mirror_threatfox_swap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic runs without the app pool's search_path, so qualify explicitly.
    # CHECK constraints mirror blocklist/infra_seed.py CLASSIFICATIONS and the
    # boolean-like `enabled` contract so direct SQL writes can't violate them.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.infra_classifications (
            id             SERIAL PRIMARY KEY,
            host           TEXT NOT NULL,
            classification TEXT NOT NULL,
            enabled        INTEGER NOT NULL DEFAULT 1,
            provenance     TEXT NOT NULL DEFAULT 'curated',
            reason         TEXT NOT NULL DEFAULT '',
            notes          TEXT NOT NULL DEFAULT '',
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            UNIQUE (host),
            CONSTRAINT chk_infra_classifications_classification CHECK (
                classification IN (
                    'LEGITIMATE_DOMAIN',
                    'SHARED_LEGITIMATE_INFRASTRUCTURE',
                    'TRUSTED_SERVICE',
                    'UNKNOWN'
                )
            ),
            CONSTRAINT chk_infra_classifications_enabled CHECK (enabled IN (0, 1))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_infra_classifications_class "
        "ON app.infra_classifications (classification)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_infra_classifications_enabled "
        "ON app.infra_classifications (enabled)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.infra_classifications")
