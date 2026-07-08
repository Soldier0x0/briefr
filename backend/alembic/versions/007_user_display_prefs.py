"""Display preferences and timezone on user_preferences (Wave 2 PR 5).

Revision ID: 007_user_display_prefs
"""

from __future__ import annotations

from alembic import op

revision = "007_user_display_prefs"
down_revision = "006_user_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS display_prefs_json TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'UTC'
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS timezone")
    op.execute("ALTER TABLE user_preferences DROP COLUMN IF EXISTS display_prefs_json")
