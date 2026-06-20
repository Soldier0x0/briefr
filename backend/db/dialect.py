"""SQL dialect helpers for dual SQLite / PostgreSQL support."""

from __future__ import annotations

import re

from db.config import is_postgres

# SQLite ``datetime('now')`` stores UTC-ish text timestamps in BRIEFR.
_NOW_UTC_TEXT = (
    "(TO_CHAR((NOW() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS'))"
)


def adapt_sql(sql: str, *, backend: str | None = None) -> str:
    """Translate SQLite-oriented SQL for PostgreSQL when needed."""
    use_postgres = (
        backend == "postgresql" if backend is not None else is_postgres()
    )
    if not use_postgres:
        return sql

    text = sql.strip()
    upper = text.upper()
    if upper.startswith("PRAGMA INTEGRITY_CHECK"):
        return "SELECT 'ok' AS integrity_check"
    if upper.startswith("PRAGMA FOREIGN_KEY_CHECK"):
        return "SELECT '' AS foreign_key_check WHERE FALSE"
    text = re.sub(r"\bdatetime\('now'\)", _NOW_UTC_TEXT, text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bdatetime\('now',\s*([^)]+)\)",
        r"((NOW() AT TIME ZONE 'utc') + CAST(\1 AS interval))",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bdate\('now',\s*([^)]+)\)",
        r"(((NOW() AT TIME ZONE 'utc') + CAST(\1 AS interval))::date)",
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
        r"\bdate\((\w+)\)",
        r"\1::date",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"datetime\((\w+)\)\s*>\s*datetime\('now'\)",
        r"\1::timestamp > (NOW() AT TIME ZONE 'utc')",
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
    text = _qmark_to_dollar(text)
    return text


def adapt_params(params: tuple | list | dict) -> tuple | dict:
    """Pass dict (named ``:name``-style) params through unchanged — sqlite3
    binds them natively. Converting to tuple(params) would silently bind the
    dict's *keys* instead of its values, and break if the dict has any extra
    keys the SQL doesn't reference (sqlite3.ProgrammingError: incorrect
    number of bindings)."""
    if isinstance(params, dict):
        return params
    return tuple(params)


def _qmark_to_dollar(sql: str) -> str:
    """Convert SQLite ``?`` placeholders to PostgreSQL ``$n``."""
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
