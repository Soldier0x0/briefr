"""PostgreSQL SQL adaptation for legacy SQLite-oriented query strings.

Internal to ``db/connection.py`` — routers and auth repos still emit ``?`` /
``datetime('now')`` SQL; ``PostgresConnection`` translates at the boundary.
All ``db/*.py`` modules use native ``$n``/``?`` constants directly (Post-B Phase 1).
"""

from __future__ import annotations

import re
from functools import lru_cache

from db.config import is_postgres

_NOW_UTC_TEXT = "(TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS'))"


def _postgres_translate_sql(text: str) -> str:
    """SQLite-oriented SQL → PostgreSQL syntax (placeholders handled separately)."""
    upper = text.upper()
    if upper.startswith("PRAGMA INTEGRITY_CHECK"):
        return "SELECT 'ok' AS integrity_check"
    if upper.startswith("PRAGMA FOREIGN_KEY_CHECK"):
        return "SELECT '' AS foreign_key_check WHERE FALSE"

    def _datetime_compare(match: re.Match[str]) -> str:
        col, op, interval = match.group(1), match.group(2), match.group(3)
        rhs = "(NOW() AT TIME ZONE 'utc')"
        if interval:
            rhs = f"({rhs} + CAST(CAST({interval} AS text) AS interval))"
        return f"{col}::timestamp {op} {rhs}"

    text = re.sub(
        r"\bdatetime\((\w+(?:\.\w+)?)\)\s*(>=|<=|>|<|=)\s*datetime\('now'(?:,\s*([^)]+))?\)",
        _datetime_compare,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bdatetime\('now'\)", _NOW_UTC_TEXT, text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bdatetime\('now',\s*([^)]+)\)",
        r"(TO_CHAR(((NOW() AT TIME ZONE 'utc') + CAST(CAST(\1 AS text) AS interval)), 'YYYY-MM-DD HH24:MI:SS'))",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\(\s*julianday\('now'\)\s*-\s*julianday\((\w+)\)\s*\)\s*\*\s*86400",
        r"EXTRACT(EPOCH FROM ((NOW() AT TIME ZONE 'utc') - CAST(\1 AS timestamp)))",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdate\('now',\s*([^)]+)\)",
        r"(((NOW() AT TIME ZONE 'utc') + CAST(CAST(\1 AS text) AS interval))::date)",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdate\('now'\)",
        r"((NOW() AT TIME ZONE 'utc')::date)",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdate\((\w+(?:\.\w+)?)\)",
        r"\1::date",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdatetime\((\w+(?:\.\w+)?)\)",
        r"\1::timestamp",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+epss_history\b",
        "INSERT INTO epss_history",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if re.search(r"INSERT\s+INTO\s+epss_history\b", text, re.IGNORECASE) and (
        "ON CONFLICT" not in text.upper()
    ):
        text = (
            text.rstrip(";")
            + " ON CONFLICT (cve_id, recorded_date) DO UPDATE SET "
            "score = EXCLUDED.score"
        )
    if re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", text, re.IGNORECASE):
        text = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        if "ON CONFLICT" not in text.upper():
            text = text.rstrip(";") + " ON CONFLICT DO NOTHING"
    return text


def adapt_sql(sql: str, *, backend: str | None = None) -> str:
    """Translate SQLite-oriented SQL for PostgreSQL when needed."""
    use_postgres = backend == "postgresql" if backend is not None else is_postgres()
    if not use_postgres:
        return sql
    text = _postgres_translate_sql(sql.strip())
    text, _ = _colon_to_dollar(text)
    return _qmark_to_dollar(text)


def prepare_query(
    sql: str,
    params: tuple | list | dict = (),
    *,
    backend: str | None = None,
) -> tuple[str, tuple | dict]:
    """Return SQL + params ready for PostgreSQL asyncpg."""
    use_postgres = backend == "postgresql" if backend is not None else is_postgres()
    if not use_postgres:
        return sql, adapt_params(params)
    text = _postgres_translate_sql(sql.strip())
    text, names = _colon_to_dollar(text)
    text = _qmark_to_dollar(text)
    if isinstance(params, dict):
        if names:
            return text, tuple(params[name] for name in names)
        return text, tuple(params.values())
    if isinstance(params, list):
        return text, tuple(params)
    return text, params


def adapt_params(params: tuple | list | dict) -> tuple | dict:
    if isinstance(params, dict):
        return params
    return tuple(params)


@lru_cache(maxsize=1024)
def _colon_to_dollar(sql: str) -> tuple[str, tuple[str, ...]]:
    if ":" not in sql:
        return sql, ()
    out: list[str] = []
    names: list[str] = []
    index = 0
    n = 1
    while index < len(sql):
        ch = sql[index]
        if ch == "'" or ch == '"':
            quote = ch
            out.append(ch)
            index += 1
            while index < len(sql):
                out.append(sql[index])
                if sql[index] == quote and sql[index - 1] != "\\":
                    index += 1
                    break
                index += 1
            continue
        if ch == ":" and index + 1 < len(sql) and sql[index + 1] == ":":
            out.append("::")
            index += 2
            continue
        if ch == ":" and index + 1 < len(sql):
            j = index + 1
            while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            name = sql[index + 1 : j]
            if name:
                names.append(name)
                out.append(f"${n}")
                n += 1
                index = j
                continue
        out.append(ch)
        index += 1
    return "".join(out), tuple(names)


def _qmark_to_dollar(sql: str) -> str:
    if "?" not in sql:
        return sql
    out: list[str] = []
    index = 0
    n = 1
    while index < len(sql):
        ch = sql[index]
        if ch == "?":
            out.append(f"${n}")
            n += 1
            index += 1
            continue
        if ch == "'" or ch == '"':
            quote = ch
            out.append(ch)
            index += 1
            while index < len(sql):
                out.append(sql[index])
                if sql[index] == quote and sql[index - 1] != "\\":
                    index += 1
                    break
                index += 1
            continue
        out.append(ch)
        index += 1
    return "".join(out)
