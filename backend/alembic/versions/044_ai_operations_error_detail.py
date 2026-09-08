"""Add error_detail on ai_operations for operator-visible failure excerpts.

Revision ID: 044_ai_operations_error_detail
Revises: 043_ioc_value_digest
"""

from __future__ import annotations

from alembic import op

revision = "044_ai_operations_error_detail"
down_revision = "043_ioc_value_digest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.ai_operations ADD COLUMN IF NOT EXISTS error_detail TEXT"
    )
