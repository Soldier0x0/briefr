"""Per-user in-app notification inbox (analyst + operator scopes).

Revision ID: 015_user_notifications
"""

from __future__ import annotations

from alembic import op

revision = "015_user_notifications"
down_revision = "014_ai_operations"
branch_labels = None
depends_on = None

_TS = "timezone('utc', now())::text"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            scope TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            entity_type TEXT NOT NULL DEFAULT '',
            entity_id TEXT NOT NULL DEFAULT '',
            dedupe_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({_TS}),
            read_at TEXT,
            dismissed_at TEXT,
            UNIQUE (user_id, dedupe_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_notifications_user_active "
        "ON user_notifications(user_id, dismissed_at, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_notifications_unread "
        "ON user_notifications(user_id, read_at) WHERE dismissed_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_notifications_unread")
    op.execute("DROP INDEX IF EXISTS idx_user_notifications_user_active")
    op.execute("DROP TABLE IF EXISTS user_notifications")
