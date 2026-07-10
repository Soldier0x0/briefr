"""AI operations observability log (AI-1).

Revision ID: 014_ai_operations
"""

from __future__ import annotations

from alembic import op

revision = "014_ai_operations"
down_revision = "013_webhook_destination_dedupe"
branch_labels = None
depends_on = None

_TS = "timezone('utc', now())::text"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ai_operations (
            id SERIAL PRIMARY KEY,
            operation_id TEXT NOT NULL,
            request_id TEXT,
            started_at TEXT DEFAULT ({_TS}),
            latency_ms INTEGER,
            feature TEXT NOT NULL,
            task_class TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            error_class TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd REAL,
            fallback_from_provider TEXT,
            fallback_from_model TEXT,
            retry_index INTEGER NOT NULL DEFAULT 0,
            context_type TEXT,
            context_id TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_operations_started ON ai_operations(started_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_operations_task_provider "
        "ON ai_operations(task_class, provider)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ai_operations_task_provider")
    op.execute("DROP INDEX IF EXISTS idx_ai_operations_started")
    op.execute("DROP TABLE IF EXISTS ai_operations")
