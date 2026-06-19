"""Tests for SQL dialect adaptation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.dialect import adapt_sql


def test_qmark_to_dollar():
    sql = adapt_sql("SELECT * FROM cves WHERE cve_id = ?", backend="postgresql")
    assert sql == "SELECT * FROM cves WHERE cve_id = $1"


def test_datetime_now_replaced():
    sql = adapt_sql(
        "INSERT INTO watchlist (cve_id, created_at) VALUES (?, datetime('now'))",
        backend="postgresql",
    )
    assert "datetime('now')" not in sql
    assert "$1" in sql


def test_insert_or_ignore():
    sql = adapt_sql(
        "INSERT OR IGNORE INTO api_usage (service, date_utc, month_utc, count) VALUES (?, ?, ?, ?)",
        backend="postgresql",
    )
    assert "INSERT OR IGNORE" not in sql.upper()
    assert "ON CONFLICT DO NOTHING" in sql


def test_pragma_integrity_check():
    sql = adapt_sql("PRAGMA integrity_check", backend="postgresql")
    assert sql.startswith("SELECT 'ok'")
