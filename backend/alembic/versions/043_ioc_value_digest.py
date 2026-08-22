"""Fixed-width ioc_value_digest for btree index lookups on long IOC values.

PhishTank/URLhaus URLs can exceed PostgreSQL btree index entry limits (~2704 B).
Replace (ioc_type, ioc_value) indexes with (ioc_type, ioc_value_digest) where
digest = md5(lower(ioc_value)). OTX pulse IOC PK becomes
(pulse_id, ioc_type, ioc_value_digest).

Revision ID: 043_ioc_value_digest
Revises: 042_publication_events_actors
"""

from __future__ import annotations

from alembic import op

revision = "043_ioc_value_digest"
down_revision = "042_publication_events_actors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- app.ti_mirror_iocs (catalog mirror) ---
    op.execute(
        "ALTER TABLE app.ti_mirror_iocs "
        "ADD COLUMN IF NOT EXISTS ioc_value_digest TEXT"
    )
    op.execute(
        """
        UPDATE app.ti_mirror_iocs
        SET ioc_value_digest = md5(lower(ioc_value))
        WHERE ioc_value_digest IS NULL OR ioc_value_digest = ''
        """
    )
    op.execute(
        "ALTER TABLE app.ti_mirror_iocs "
        "ALTER COLUMN ioc_value_digest SET NOT NULL"
    )
    op.execute("DROP INDEX IF EXISTS app.idx_ti_mirror_type_value")
    op.execute("DROP INDEX IF EXISTS idx_ti_mirror_type_value")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ti_mirror_type_digest "
        "ON app.ti_mirror_iocs (ioc_type, ioc_value_digest)"
    )

    # --- intel.otx_pulse_iocs (OTX pulse indicators) ---
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "ADD COLUMN IF NOT EXISTS ioc_value_digest TEXT"
    )
    op.execute(
        """
        UPDATE intel.otx_pulse_iocs
        SET ioc_value_digest = md5(lower(ioc_value))
        WHERE ioc_value_digest IS NULL OR ioc_value_digest = ''
        """
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "ALTER COLUMN ioc_value_digest SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "DROP CONSTRAINT IF EXISTS otx_pulse_iocs_pkey"
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "ADD PRIMARY KEY (pulse_id, ioc_type, ioc_value_digest)"
    )
    op.execute("DROP INDEX IF EXISTS intel.idx_otx_pulse_iocs_type_value")
    op.execute("DROP INDEX IF EXISTS idx_otx_pulse_iocs_type_value")
    op.execute("DROP INDEX IF EXISTS intel.idx_otx_pulse_iocs_value")
    op.execute("DROP INDEX IF EXISTS idx_otx_pulse_iocs_value")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_type_digest "
        "ON intel.otx_pulse_iocs (ioc_type, ioc_value_digest)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS intel.idx_otx_pulse_iocs_type_digest")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_type_value "
        "ON intel.otx_pulse_iocs (ioc_type, ioc_value)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_otx_pulse_iocs_value "
        "ON intel.otx_pulse_iocs (ioc_value)"
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "DROP CONSTRAINT IF EXISTS otx_pulse_iocs_pkey"
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "ADD PRIMARY KEY (pulse_id, ioc_type, ioc_value)"
    )
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs DROP COLUMN IF EXISTS ioc_value_digest"
    )

    op.execute("DROP INDEX IF EXISTS app.idx_ti_mirror_type_digest")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ti_mirror_type_value "
        "ON app.ti_mirror_iocs (ioc_type, ioc_value)"
    )
    op.execute(
        "ALTER TABLE app.ti_mirror_iocs DROP COLUMN IF EXISTS ioc_value_digest"
    )
