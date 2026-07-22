"""AI operation failure payload storage table (Program E Task 1).

Revision ID: 034_ai_operation_payloads
Revises: 033_search_api_tokens
Create Date: 2026-07-22
"""

from __future__ import annotations

from alembic import op

revision = "034_ai_operation_payloads"
down_revision = "033_search_api_tokens"
branch_labels = None
depends_on = None

_TS = "timezone('utc', now())::text"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ai_operation_payloads (
            operation_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT ({_TS}),
            messages_json TEXT NOT NULL,
            response_excerpt TEXT,
            task_class TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_operation_payloads_created "
        "ON ai_operation_payloads(created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ai_operation_payloads_created")
    op.execute("DROP TABLE IF EXISTS ai_operation_payloads")
