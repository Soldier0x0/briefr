"""Opt-in storage for failed LLM request payloads (Program E)."""

from __future__ import annotations

import os
from typing import Any

from db.types import DbConnection

_STORE_FAILURE_PAYLOADS_DISABLED = {
    "",
    "0",
    "false",
    "no",
    "off",
}

_SECRET_ENV_SUFFIXES = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
)

_TRUNCATED_SUFFIX = "...[truncated]"

_INSERT_SQLITE = """
INSERT INTO ai_operation_payloads (
    operation_id,
    messages_json,
    response_excerpt,
    task_class,
    provider,
    model
) VALUES (?, ?, ?, ?, ?, ?)
"""

_INSERT_PG = """
INSERT INTO ai_operation_payloads (
    operation_id,
    messages_json,
    response_excerpt,
    task_class,
    provider,
    model
) VALUES ($1, $2, $3, $4, $5, $6)
"""

_SELECT_BY_OPERATION_ID_SQLITE = """
SELECT operation_id, created_at, messages_json, response_excerpt, task_class, provider, model
FROM ai_operation_payloads
WHERE operation_id = ?
LIMIT 1
"""

_SELECT_BY_OPERATION_ID_PG = """
SELECT operation_id, created_at, messages_json, response_excerpt, task_class, provider, model
FROM ai_operation_payloads
WHERE operation_id = $1
LIMIT 1
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def store_failure_payloads_enabled() -> bool:
    value = os.environ.get("AI_OPERATIONS_STORE_FAILURE_PAYLOADS", "0")
    return value.strip().lower() not in _STORE_FAILURE_PAYLOADS_DISABLED


def _truncate(value: str, limit: int = 32_768) -> str:
    if len(value) <= limit:
        return value
    if limit <= len(_TRUNCATED_SUFFIX):
        return _TRUNCATED_SUFFIX[:limit]
    return value[: limit - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


def _secret_values() -> list[str]:
    values: set[str] = set()
    for key, value in os.environ.items():
        if not value:
            continue
        upper = key.upper()
        if upper.endswith(_SECRET_ENV_SUFFIXES):
            values.add(value)
    return sorted(values, key=len, reverse=True)


def _redact_secrets(value: str) -> str:
    redacted = value
    for secret in _secret_values():
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


async def insert_ai_operation_payload(
    db: DbConnection,
    *,
    operation_id: str,
    messages_json: str,
    response_excerpt: str | None,
    task_class: str,
    provider: str,
    model: str,
) -> None:
    pg = _is_postgres_connection(db)
    cleaned_messages = _truncate(_redact_secrets(messages_json))
    cleaned_excerpt = (
        _truncate(_redact_secrets(response_excerpt))
        if response_excerpt is not None
        else None
    )
    params: tuple[Any, ...] = (
        operation_id,
        cleaned_messages,
        cleaned_excerpt,
        task_class,
        provider,
        model,
    )
    sql = _INSERT_PG if pg else _INSERT_SQLITE
    await db.execute(sql, params)


async def get_ai_operation_payload(
    db: DbConnection,
    *,
    operation_id: str,
) -> dict[str, Any] | None:
    pg = _is_postgres_connection(db)
    sql = _SELECT_BY_OPERATION_ID_PG if pg else _SELECT_BY_OPERATION_ID_SQLITE
    rows = await db.execute_fetchall(sql, (operation_id,))
    if not rows:
        return None
    return dict(rows[0])
