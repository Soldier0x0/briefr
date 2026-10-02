"""Investigation workspace cases (saved graph snapshots).

Revision ID: 045_investigation_cases
Revises: 044_ai_operations_error_detail
"""

from __future__ import annotations

from alembic import op

revision = "045_investigation_cases"
down_revision = "044_ai_operations_error_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic runs without the app pool search_path; qualify app schema explicitly.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.investigation_cases (
            id UUID PRIMARY KEY,
            owner_user_id INTEGER NOT NULL REFERENCES app.users(id),
            title TEXT NOT NULL,
            root_node_id TEXT NOT NULL,
            snapshot JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_investigation_cases_owner_updated "
        "ON app.investigation_cases (owner_user_id, updated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS app.ix_investigation_cases_owner_updated")
    op.execute("DROP TABLE IF EXISTS app.investigation_cases")
