"""Built-in app login (decision 2026-06-11): users + sessions.

Revision ID: 002_users_sessions
"""

from __future__ import annotations

from alembic import op

revision = "002_users_sessions"
down_revision = "001_initial"
branch_labels = None
depends_on = None

_TS = "TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT ({_TS}),
            last_login_at TEXT
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            refresh_token_hash TEXT NOT NULL,
            created_at TEXT DEFAULT ({_TS}),
            last_used_at TEXT DEFAULT ({_TS}),
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            user_agent TEXT DEFAULT '',
            ip TEXT DEFAULT '',
            remember_me INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(refresh_token_hash)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
