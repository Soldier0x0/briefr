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
               latency_ms, retry_index, started_at, context_type, context_id,
               fallback_from_provider, fallback_from_model
        FROM ai_operations
        ORDER BY id DESC
        LIMIT {limit_ph}
        """,
        (limit,),
    )
    return [dict(row) for row in rows]


def _hours_ago_iso(hours: int) -> str:
    from datetime import datetime, timedelta, timezone

    ts = datetime.now(timezone.utc) - timedelta(hours=hours)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


async def ai_operations_usage_since(
    db: DbConnection,
    *,
    hours: int,
) -> dict:
    since = _hours_ago_iso(hours)
    pg = _is_postgres_connection(db)
    since_ph = "$1" if pg else "?"

    totals = await db.execute_fetchall(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
            SUM(CASE WHEN fallback_from_provider IS NOT NULL AND success = 1
                THEN 1 ELSE 0 END) AS fallback_successes
        FROM ai_operations
        WHERE started_at >= {since_ph}
        """,
        (since,),
    )
    row = dict(totals[0]) if totals else {}
    total = int(row.get("total") or 0)
    successes = int(row.get("successes") or 0)
    failures = int(row.get("failures") or 0)
    fallback_successes = int(row.get("fallback_successes") or 0)
    failure_rate = round(failures / total, 4) if total else 0.0

    by_provider_rows = await db.execute_fetchall(
        f"""
        SELECT provider,
               COUNT(*) AS total,
               SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes
        FROM ai_operations
        WHERE started_at >= {since_ph}
        GROUP BY provider
        ORDER BY total DESC
        """,
        (since,),
    )
    by_task_rows = await db.execute_fetchall(
        f"""
        SELECT task_class,
               COUNT(*) AS total,
               SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes
        FROM ai_operations
        WHERE started_at >= {since_ph}
        GROUP BY task_class
        ORDER BY total DESC
        """,
        (since,),
    )

    return {
        "hours": hours,
        "since": since,
        "total": total,
        "successes": successes,
        "failures": failures,
        "failure_rate": failure_rate,
        "fallback_successes": fallback_successes,
        "by_provider": [dict(r) for r in by_provider_rows],
        "by_task": [dict(r) for r in by_task_rows],
        "tokens_recorded": False,
    }


async def list_ai_operations_page(
    db: DbConnection,
    *,
    limit: int = 50,
    offset: int = 0,
    task_class: str | None = None,
    provider: str | None = None,
) -> tuple[list[dict], int]:
    pg = _is_postgres_connection(db)
    clauses: list[str] = []
    params: list[Any] = []

    if task_class:
        clauses.append(f"task_class = {'$' + str(len(params) + 1) if pg else '?'}")
        params.append(task_class)
    if provider:
        clauses.append(f"provider = {'$' + str(len(params) + 1) if pg else '?'}")
        params.append(provider)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    count_rows = await db.execute_fetchall(
        f"SELECT COUNT(*) AS cnt FROM ai_operations {where}",
        tuple(params),
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0

    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    if pg:
        limit_ph = f"${limit_idx}"
        offset_ph = f"${offset_idx}"
    else:
        limit_ph = "?"
        offset_ph = "?"
    params.extend([limit, offset])

    rows = await db.execute_fetchall(
        f"""
        SELECT operation_id, task_class, provider, model, success, error_class,
               latency_ms, retry_index, started_at, context_type, context_id,
               fallback_from_provider, fallback_from_model
        FROM ai_operations
        {where}
        ORDER BY id DESC
        LIMIT {limit_ph} OFFSET {offset_ph}
        """,
        tuple(params),
    )
    return [dict(row) for row in rows], total


async def count_cve_embeddings(db: DbConnection) -> int:
    rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM cve_embeddings")
    return int(dict(rows[0])["cnt"]) if rows else 0
