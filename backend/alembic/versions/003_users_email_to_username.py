"""Rename users.email to users.username (login identifier).

Revision ID: 003_users_email_to_username
"""

from __future__ import annotations

from alembic import op

revision = "003_users_email_to_username"
down_revision = "002_users_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh installs that already have `username` skip the rename.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'email'
            ) THEN
                ALTER TABLE users RENAME COLUMN email TO username;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'username'
            ) THEN
                ALTER TABLE users RENAME COLUMN username TO email;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_users_username")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
