"""Apply Procrastinate durable-job schema (Q1).

Revision ID: 028_procrastinate_schema
Revises: 027_alembic_version_num_widen
Create Date: 2026-07-17
"""

from __future__ import annotations

from alembic import op

revision = "028_procrastinate_schema"
down_revision = "027_alembic_version_num_widen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from procrastinate.schema import SchemaManager

    sql = SchemaManager.get_schema()
    conn = op.get_bind()
    # Literal SQL (includes :: casts) — do not use text()/bind parsing.
    #
    # The vendored Procrastinate DDL contains PL/pgSQL RAISE format strings
    # such as `RAISE '... (job id: %)', job_id;`. exec_driver_sql still passes
    # the statement through the DBAPI driver's own placeholder parser, and the
    # production psycopg3 driver reads `%` as a query-parameter marker — `%)`
    # is not a valid one, so the whole statement is rejected
    # ("only '%s', '%b', '%t' are allowed as placeholders, got '%)'"). Doubling
    # every literal `%` to `%%` is psycopg's escape for a literal percent; the
    # driver un-doubles it back to `%` before sending to Postgres, so the
    # stored functions keep their intended `... (job id: %)` text. The schema
    # has no real bind parameters, so escaping every `%` is safe.
    conn.exec_driver_sql(sql.replace("%", "%%"))


def downgrade() -> None:
    # Leaving Procrastinate objects in place on downgrade is intentional —
    # dropping them while deferred jobs may exist is unsafe.
    pass
