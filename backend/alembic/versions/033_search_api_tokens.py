"""Search API tokens table (Embeddings E5).

Revision ID: 033_search_api_tokens
Revises: 032_embeddings_pgvector
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op

revision = "033_search_api_tokens"
down_revision = "032_embeddings_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_api_tokens (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            token_prefix TEXT NOT NULL UNIQUE,
            token_hash TEXT NOT NULL,
            scopes TEXT NOT NULL DEFAULT '["search:semantic","cves:related","cves:read"]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by TEXT NOT NULL DEFAULT '',
            last_used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_api_tokens_prefix "
        "ON search_api_tokens (token_prefix) WHERE revoked_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search_api_tokens")
