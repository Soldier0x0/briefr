"""Persist redacted LLM operation rows (AI-1). Postgres-native with SQLite parity."""

from __future__ import annotations

from typing import Any

from db.timeutil import utcnow_str
from db.types import DbConnection

_INSERT_SQLITE = """
INSERT INTO ai_operations (
    operation_id, request_id, started_at, latency_ms, feature, task_class,
    provider, model, success, error_class, input_tokens, output_tokens,
    total_tokens, estimated_cost_usd, fallback_from_provider, fallback_from_model,
    retry_index, context_type, context_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_PG = """
INSERT INTO ai_operations (
    operation_id, request_id, started_at, latency_ms, feature, task_class,
    provider, model, success, error_class, input_tokens, output_tokens,
    total_tokens, estimated_cost_usd, fallback_from_provider, fallback_from_model,
    retry_index, context_type, context_id
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
)
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


async def insert_ai_operation(
    db: DbConnection,
    *,
    operation_id: str,
    request_id: str | None,
    started_at: str,
    latency_ms: int,
    feature: str,
    task_class: str,
    provider: str,
    model: str,
    success: bool,
    error_class: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    fallback_from_provider: str | None = None,
    fallback_from_model: str | None = None,
    retry_index: int = 0,
    context_type: str | None = None,
    context_id: str | None = None,
) -> None:
    pg = _is_postgres_connection(db)
    params: tuple[Any, ...] = (
        operation_id,
        request_id,
        started_at,
        latency_ms,
        feature,
        task_class,
        provider,
        model,
        success if pg else int(success),
        error_class,
        input_tokens,
        output_tokens,
        total_tokens,
        estimated_cost_usd,
        fallback_from_provider,
        fallback_from_model,
        retry_index,
        context_type,
        context_id,
    )
    sql = _INSERT_PG if pg else _INSERT_SQLITE
    await db.execute(sql, params)


async def count_ai_operations(db: DbConnection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM ai_operations")
    return int(rows[0]["cnt"]) if rows else 0


async def list_ai_operations(
    db: DbConnection,
    *,
    limit: int = 50,
) -> list[dict]:
    pg = _is_postgres_connection(db)
    limit_ph = "$1" if pg else "?"
    rows = await db.execute_fetchall(
        f"""
        SELECT operation_id, task_class, provider, model, success, error_class,
               latency_ms, retry_index, started_at
        FROM ai_operations
        ORDER BY id DESC
        LIMIT {limit_ph}
        """,
        (limit,),
    )
    return [dict(row) for row in rows]
