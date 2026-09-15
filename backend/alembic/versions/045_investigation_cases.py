"""Investigation workspace cases (saved graph snapshots).

Revision ID: 045_investigation_cases
Revises: 044_ai_operations_error_detail
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "045_investigation_cases"
down_revision = "044_ai_operations_error_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        id_type = postgresql.UUID(as_uuid=False)
        snapshot_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        id_type = sa.String(36)
        snapshot_type = sa.Text()

    op.create_table(
        "investigation_cases",
        sa.Column("id", id_type, primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("root_node_id", sa.Text(), nullable=False),
        sa.Column("snapshot", snapshot_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_investigation_cases_owner_updated",
        "investigation_cases",
        ["owner_user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigation_cases_owner_updated", table_name="investigation_cases")
    op.drop_table("investigation_cases")
