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


def test_datetime_now_interval():
    sql = adapt_sql(
        "SELECT * FROM ioc_cache WHERE cached_at > datetime('now', '-6 hours')",
        backend="postgresql",
    )
    assert "CAST('-6 hours' AS interval)" in sql


def test_date_now_interval():
    sql = adapt_sql(
        "SELECT * FROM cves WHERE DATE(published) >= DATE('now', ?)",
        backend="postgresql",
    )
    assert "published::date" in sql
    assert "CAST($1 AS interval)" in sql


def test_named_params_to_dollar():
    from db.dialect import prepare_query

    sql = """
        INSERT INTO cves (cve_id, description, cvss_score)
        VALUES (:cve_id, :description, :cvss_score)
    """
    adapted, params = prepare_query(
        sql,
        {"cve_id": "CVE-2024-1", "description": "test", "cvss_score": 9.8},
        backend="postgresql",
    )
    assert ":cve_id" not in adapted
    assert "$1" in adapted and "$3" in adapted
    assert params == ("CVE-2024-1", "test", 9.8)
