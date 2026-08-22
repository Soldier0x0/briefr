"""Fixed-width ioc_value_digest for btree index lookups on long IOC values.

PhishTank/URLhaus URLs can exceed PostgreSQL btree index entry limits (~2704 B).
Replace (ioc_type, ioc_value) indexes with (lower(ioc_type), ioc_value_digest)
where digest = md5(trim(ioc_value)) on canonical stored values. OTX pulse IOC PK
becomes (pulse_id, ioc_type, ioc_value_digest).

Downgrade is intentionally unsupported when oversized URL rows exist.

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
        SET ioc_value_digest = md5(trim(ioc_value))
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
        "ON app.ti_mirror_iocs (lower(ioc_type), ioc_value_digest)"
    )

    # --- intel.otx_pulse_iocs (OTX pulse indicators) ---
    op.execute(
        "ALTER TABLE intel.otx_pulse_iocs "
        "ADD COLUMN IF NOT EXISTS ioc_value_digest TEXT"
    )
    op.execute(
        """
        UPDATE intel.otx_pulse_iocs
        SET ioc_value_digest = md5(trim(ioc_value))
        WHERE ioc_value_digest IS NULL OR ioc_value_digest = ''
        """
    )
    # Collapse legacy rows that would share a digest key before the PK swap.
    op.execute(
        """
        DELETE FROM intel.otx_pulse_iocs a
        USING intel.otx_pulse_iocs b
        WHERE a.ctid < b.ctid
          AND a.pulse_id = b.pulse_id
          AND a.ioc_type = b.ioc_type
          AND a.ioc_value_digest = b.ioc_value_digest
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
        "ON intel.otx_pulse_iocs (lower(ioc_type), ioc_value_digest)"
    )

    # Auto-populate digest on any write path (tests, legacy SQL, ad-hoc inserts).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.set_ioc_value_digest()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.ioc_value_digest IS NULL OR NEW.ioc_value_digest = '' THEN
                NEW.ioc_value_digest := md5(trim(NEW.ioc_value));
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER ti_mirror_iocs_digest_trg
        BEFORE INSERT OR UPDATE OF ioc_value ON app.ti_mirror_iocs
        FOR EACH ROW EXECUTE FUNCTION app.set_ioc_value_digest()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION intel.set_ioc_value_digest()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.ioc_value_digest IS NULL OR NEW.ioc_value_digest = '' THEN
                NEW.ioc_value_digest := md5(trim(NEW.ioc_value));
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER otx_pulse_iocs_digest_trg
        BEFORE INSERT OR UPDATE OF ioc_value ON intel.otx_pulse_iocs
        FOR EACH ROW EXECUTE FUNCTION intel.set_ioc_value_digest()
        """
    )


def downgrade() -> None:
    raise NotImplementedError(
        "043_ioc_value_digest downgrade is unsupported: oversized URL rows cannot "
        "be re-indexed on raw ioc_value btree columns (PostgreSQL ~2704 B limit)."
    )
