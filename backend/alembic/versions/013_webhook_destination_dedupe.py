"""Per-destination webhook dedupe store (PR12b).

Revision ID: 013_webhook_destination_dedupe
"""

from __future__ import annotations

from alembic import op

revision = "013_webhook_destination_dedupe"
down_revision = "012_cve_trgm_search"
branch_labels = None
depends_on = None

_TS = "timezone('utc', now())::text"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS webhook_destination_dedupe (
            destination_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            dedupe_key TEXT NOT NULL,
            recorded_at TEXT DEFAULT ({_TS}),
            PRIMARY KEY (destination_id, event_type, dedupe_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_dest_dedupe_event "
        "ON webhook_destination_dedupe(event_type, dedupe_key)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_webhook_dest_dedupe_event")
    op.execute("DROP TABLE IF EXISTS webhook_destination_dedupe")
