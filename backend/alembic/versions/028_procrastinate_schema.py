"""Apply Procrastinate durable-job schema (Q1).

Revision ID: 028_procrastinate_schema
Revises: 027_alembic_version_num_widen
Create Date: 2026-07-17
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "028_procrastinate_schema"
down_revision = "027_alembic_version_num_widen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from procrastinate.schema import SchemaManager

    sql = SchemaManager.get_schema()
    conn = op.get_bind()
    # Raw script (DO $$ … ENUM … CREATE TABLE). Avoid Alembic % bind rules.
    conn.execute(text(sql))


def downgrade() -> None:
    # Leaving Procrastinate objects in place on downgrade is intentional —
    # dropping them while deferred jobs may exist is unsafe.
    pass
