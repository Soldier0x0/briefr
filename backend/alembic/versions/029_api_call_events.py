"""api_call_events + api_usage.last_called_at (Q2 metering).

Revision ID: 029_api_call_events
Revises: 028_procrastinate_schema
Create Date: 2026-07-17
"""

from __future__ import annotations

from alembic import op

revision = "029_api_call_events"
down_revision = "028_procrastinate_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_call_events (
            id BIGSERIAL PRIMARY KEY,
            ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source TEXT NOT NULL,
            pacing_key TEXT,
            method TEXT NOT NULL,
            host TEXT,
            path_template TEXT,
            status_code INTEGER,
            ok BOOLEAN NOT NULL DEFAULT FALSE,
            latency_ms INTEGER,
            actor_type TEXT,
            actor_id TEXT,
            job_id TEXT,
            run_id TEXT,
            queue_task TEXT,
            request_id TEXT,
            error_class TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_call_events_ts ON api_call_events (ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_call_events_source_ts "
        "ON api_call_events (source, ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_call_events_actor_ts "
        "ON api_call_events (actor_type, ts DESC)"
    )
    op.execute(
        """
        ALTER TABLE api_usage
        ADD COLUMN IF NOT EXISTS last_called_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_call_events_actor_ts")
    op.execute("DROP INDEX IF EXISTS idx_api_call_events_source_ts")
    op.execute("DROP INDEX IF EXISTS idx_api_call_events_ts")
    op.execute("DROP TABLE IF EXISTS api_call_events")
    op.execute("ALTER TABLE api_usage DROP COLUMN IF EXISTS last_called_at")
