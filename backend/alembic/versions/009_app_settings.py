"""Operator settings table (Phase B).

Revision ID: 009_app_settings
"""

from __future__ import annotations

from alembic import op

revision = "009_app_settings"
down_revision = "008_remember_profile"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
