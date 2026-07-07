"""Per-user stack terms and optional asset profile (Wave 2 PR 3).

Revision ID: 006_user_preferences
"""

from __future__ import annotations

from alembic import op

revision = "006_user_preferences"
down_revision = "005_epss_percentile"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            stack_terms TEXT NOT NULL DEFAULT '',
            profile_json TEXT,
            updated_at TEXT DEFAULT ({_TS})
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_preferences")
