"""Phase A: raw_ioc + host_ioc on otx_pulse_iocs (four-level IOC preservation).

raw_ioc stores the verbatim upstream IOC value; host_ioc stores the normalized
host (URL hostname or the canonical domain). Both default to '' — legacy rows
backfill host_ioc only, since the raw upstream value was never persisted.

Revision ID: 037_otx_pulse_iocs_raw_host
"""

from __future__ import annotations

from urllib.parse import urlparse

from alembic import op
from sqlalchemy import text

revision = "037_otx_pulse_iocs_raw_host"
down_revision = "036_intel_app_schema_split"
branch_labels = None
depends_on = None


def _legacy_host(ioc_type: str, ioc_value: str) -> str:
    """Frozen at migration write-time: derive host from a stored canonical
    value. Mirrors correlation.threatfox_corroboration URL→domain joins so
    backfilled host_ioc matches what read-time corroboration would derive."""
    t = (ioc_type or "").strip().upper()
    value = (ioc_value or "").strip()
    if t in ("DOMAIN", "HOSTNAME"):
        return value.lower().rstrip(".")
    if t in ("URL", "URI"):
        parsed = urlparse(value if "://" in value else f"http://{value}")
        return (parsed.hostname or "").lower().rstrip(".")
    return ""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE otx_pulse_iocs ADD COLUMN IF NOT EXISTS raw_ioc TEXT DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE otx_pulse_iocs ADD COLUMN IF NOT EXISTS host_ioc TEXT DEFAULT ''"
    )
    _backfill_host_ioc()


def _backfill_host_ioc() -> None:
    """Fill host_ioc for pre-existing rows from their canonical values.

    raw_ioc is intentionally left '' — the verbatim upstream value was never
    stored before Phase A, so it cannot be reconstructed.
    """
    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT pulse_id, ioc_type, ioc_value "
            "FROM otx_pulse_iocs WHERE host_ioc = '' OR host_ioc IS NULL"
        )
    ).mappings().all()
    if not rows:
        return
    update_sql = text(
        "UPDATE otx_pulse_iocs SET host_ioc = :host "
        "WHERE pulse_id = :pulse_id AND ioc_type = :ioc_type "
        "AND ioc_value = :ioc_value"
    )
    for row in rows:
        host = _legacy_host(row["ioc_type"], row["ioc_value"])
        if not host:
            continue
        conn.execute(
            update_sql,
            {
                "host": host,
                "pulse_id": row["pulse_id"],
                "ioc_type": row["ioc_type"],
                "ioc_value": row["ioc_value"],
            },
        )


def downgrade() -> None:
    op.execute("ALTER TABLE otx_pulse_iocs DROP COLUMN IF EXISTS host_ioc")
    op.execute("ALTER TABLE otx_pulse_iocs DROP COLUMN IF EXISTS raw_ioc")
