"""Read-only DB explorer queries — parameterized, allowlist-only."""

from __future__ import annotations

import re
import time
from typing import Any

from db.explorer_registry import (
    DEFAULT_ROW_LIMIT,
    MAX_FILTER_LEN,
    MAX_OFFSET,
    MAX_ROW_LIMIT,
    TRUNCATE_BYTES,
    TableSpec,
    list_table_specs,
    validate_table_name,
)

_CVE_ID_RE = re.compile(r"^CVE-\d{4}-\d{4,7}$", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

_COUNT_ALL_SQLITE = "SELECT COUNT(*) AS cnt FROM {table}"
_COUNT_ALL_PG = "SELECT COUNT(*) AS cnt FROM {table}"
_COUNT_FILTER_SQLITE = "SELECT COUNT(*) AS cnt FROM {table} WHERE {column} = ?"
_COUNT_FILTER_PG = "SELECT COUNT(*) AS cnt FROM {table} WHERE {column} = $1"
_SELECT_ROWS_SQLITE = (
    "SELECT {columns} FROM {table}{where} ORDER BY {order_by} LIMIT ? OFFSET ?"
)
_SELECT_ROWS_PG = (
    "SELECT {columns} FROM {table}{where} ORDER BY {order_by} LIMIT $1 OFFSET $2"
)
_SELECT_ROWS_FILTER_SQLITE = (
    "SELECT {columns} FROM {table} WHERE {column} = ?"
    " ORDER BY {order_by} LIMIT ? OFFSET ?"
)
_SELECT_ROWS_FILTER_PG = (
    "SELECT {columns} FROM {table} WHERE {column} = $1"
    " ORDER BY {order_by} LIMIT $2 OFFSET $3"
)
_PG_CLASS_COUNTS_SQL = """
SELECT c.relname AS name, GREATEST(0, c.reltuples::bigint) AS cnt
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relname = ANY($1::text[])
"""

_CATALOG_COUNT_CACHE: dict[str, tuple[float, int]] = {}
CATALOG_COUNT_CACHE_TTL = 300


async def _exact_row_count(db: Any, table: str) -> int:
    sql = (
        _COUNT_ALL_PG if _is_postgres_connection(db) else _COUNT_ALL_SQLITE
    ).format(table=table)
    rows = await db.execute_fetchall(sql)
    return int(rows[0]["cnt"]) if rows else 0


async def _cached_exact_row_count(db: Any, table: str) -> int:
    now = time.monotonic()
    cached = _CATALOG_COUNT_CACHE.get(table)
    if cached and now - cached[0] < CATALOG_COUNT_CACHE_TTL:
        return cached[1]
    count = await _exact_row_count(db, table)
    _CATALOG_COUNT_CACHE[table] = (now, count)
    return count


def _is_postgres_connection(db: Any) -> bool:
    return type(db).__name__ == "PostgresConnection"


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_ROW_LIMIT
    return max(1, min(int(limit), MAX_ROW_LIMIT))


def _clamp_offset(offset: int | None) -> int:
    if offset is None:
        return 0
    return max(0, min(int(offset), MAX_OFFSET))


def _normalize_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_FILTER_LEN or "\x00" in trimmed:
        raise ValueError("Filter value too long or invalid")
    return trimmed


def _validate_cve_filter(value: str) -> None:
    if not _CVE_ID_RE.match(value):
        raise ValueError("cve_id filter must match CVE-YYYY-NNNN+ format")


def _select_list(spec: TableSpec) -> str:
    return ", ".join(spec.columns)


def _mask_cell(column: str, value: Any, spec: TableSpec) -> tuple[Any, bool]:
    """Return (value, truncated_flag)."""
    truncated = False
    if value is None:
        return None, False

    if column in spec.redact_columns:
        text = str(value)
        if _URL_RE.search(text):
            text = _URL_RE.sub("[redacted-url]", text)
        if len(text) > 80 or "token" in text.lower() or "password" in text.lower():
            return "[redacted]", truncated
        if column in spec.truncate_columns and len(text) > TRUNCATE_BYTES:
            return text[:TRUNCATE_BYTES] + "…", True
        return text, truncated

    text = value if isinstance(value, str) else str(value)
    if column in spec.truncate_columns and len(text.encode("utf-8")) > TRUNCATE_BYTES:
        encoded = text.encode("utf-8")[:TRUNCATE_BYTES]
        try:
            text = encoded.decode("utf-8")
        except UnicodeDecodeError:
            text = encoded.decode("utf-8", errors="ignore")
        return text + "…", True

    return value, truncated


def _row_to_dict(row: Any, spec: TableSpec) -> dict[str, Any]:
    out: dict[str, Any] = {}
    any_truncated = False
    keys = spec.columns
    if isinstance(row, dict):
        source = row
    elif hasattr(row, "keys"):
        source = {k: row[k] for k in row.keys()}
    else:
        source = {k: row[i] for i, k in enumerate(keys)}
    for col in keys:
        raw = source.get(col)
        masked, truncated = _mask_cell(col, raw, spec)
        out[col] = masked
        any_truncated = any_truncated or truncated
    if any_truncated:
        out["_truncated"] = True
    return out


async def fetch_table_catalog(db: Any) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    specs = list_table_specs()

    for spec in specs:
        count = await _cached_exact_row_count(db, spec.name)
        catalog.append(
            {
                "name": spec.name,
                "label": spec.label,
                "tier": spec.tier,
                "row_count": count,
                "row_count_estimated": False,
                "columns": list(spec.columns),
                "filter_columns": sorted(spec.filter_columns),
                "required_filter": spec.required_filter,
                "order_by": spec.order_by,
            }
        )
    return catalog


async def fetch_table_rows(
    db: Any,
    table: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> dict[str, Any]:
    spec = validate_table_name(table)
    if spec is None:
        raise LookupError("not_found")

    row_limit = _clamp_limit(limit)
    row_offset = _clamp_offset(offset)
    f_col = (filter_column or "").strip() or None
    f_val = _normalize_filter_value(filter_value)

    if spec.required_filter:
        if f_col != spec.required_filter or not f_val:
            raise ValueError(
                f"Table '{spec.name}' requires filter_column={spec.required_filter} "
                "with a non-empty filter_value"
            )
        if spec.required_filter == "cve_id":
            _validate_cve_filter(f_val)

    if f_col and f_col not in spec.filter_columns:
        raise ValueError(f"Filter column '{f_col}' is not allowed for this table")
    if f_col and not f_val:
        raise ValueError("filter_value is required when filter_column is set")
    if f_val and not f_col:
        raise ValueError("filter_column is required when filter_value is set")
    if f_col == "cve_id" and f_val:
        _validate_cve_filter(f_val)

    params: list[Any] = []
    pg = _is_postgres_connection(db)
    if f_col and f_val:
        count_sql = (
            _COUNT_FILTER_PG if pg else _COUNT_FILTER_SQLITE
        ).format(table=spec.name, column=f_col)
        params.append(f_val)
    else:
        count_sql = (_COUNT_ALL_PG if pg else _COUNT_ALL_SQLITE).format(table=spec.name)

    count_rows = await db.execute_fetchall(count_sql, tuple(params))
    total = int(count_rows[0]["cnt"]) if count_rows else 0

    select_columns = _select_list(spec)
    if f_col and f_val:
        select_sql = (
            _SELECT_ROWS_FILTER_PG if pg else _SELECT_ROWS_FILTER_SQLITE
        ).format(
            columns=select_columns,
            table=spec.name,
            column=f_col,
            order_by=spec.order_by,
        )
        query_params = tuple([f_val, row_limit, row_offset])
    else:
        select_sql = (_SELECT_ROWS_PG if pg else _SELECT_ROWS_SQLITE).format(
            columns=select_columns,
            table=spec.name,
            where="",
            order_by=spec.order_by,
        )
        query_params = (row_limit, row_offset)

    rows = await db.execute_fetchall(select_sql, query_params)

    return {
        "table": spec.name,
        "tier": spec.tier,
        "columns": list(spec.columns),
        "rows": [_row_to_dict(r, spec) for r in rows],
        "total": total,
        "limit": row_limit,
        "offset": row_offset,
        "filter_column": f_col,
        "filter_value": f_val,
        "has_more": row_offset + len(rows) < total,
    }
