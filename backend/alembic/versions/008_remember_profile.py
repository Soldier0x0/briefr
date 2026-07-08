"""Remember My Stack asset profile on server toggle (Wave 2 PR 6).

Revision ID: 008_remember_profile
"""

from __future__ import annotations

from alembic import op

revision = "008_remember_profile"
down_revision = "007_user_display_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS remember_profile_on_server INTEGER NOT NULL DEFAULT 0
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_preferences DROP COLUMN IF EXISTS remember_profile_on_server"
    )
