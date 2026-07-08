"""Tests for SQL dialect adaptation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.dialect import adapt_sql


def test_qmark_to_dollar():
    sql = adapt_sql("SELECT * FROM cves WHERE cve_id = ?", backend="postgresql")
    assert sql == "SELECT * FROM cves WHERE cve_id = $1"


def test_native_dollar_sql_unchanged():
    sql = adapt_sql(
        "SELECT value FROM sync_state WHERE key = $1",
        backend="postgresql",
    )
    assert sql == "SELECT value FROM sync_state WHERE key = $1"


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
    assert "CAST(CAST('-6 hours' AS text) AS interval)" in sql


def test_julianday_age_seconds():
    sql = adapt_sql(
        "SELECT CAST((julianday('now') - julianday(cached_at)) * 86400 AS INTEGER) AS age_seconds FROM ioc_cache",
        backend="postgresql",
    )
    assert "julianday" not in sql.lower()
    assert "EXTRACT(EPOCH FROM" in sql
    assert "CAST(cached_at AS timestamp)" in sql


def test_date_now_interval():
    sql = adapt_sql(
        "SELECT * FROM cves WHERE DATE(published) >= DATE('now', ?)",
        backend="postgresql",
    )
    assert "published::date" in sql
    assert "CAST(CAST($1 AS text) AS interval)" in sql


def test_datetime_column_compare_now():
    sql = adapt_sql(
        "SELECT * FROM watchlist WHERE datetime(snooze_until) > datetime('now')",
        backend="postgresql",
    )
    assert "datetime(" not in sql.lower()
    assert "snooze_until::timestamp >" in sql


def test_datetime_column_compare_now_interval():
    sql = adapt_sql(
        "SELECT * FROM cves WHERE datetime(c.modified) >= datetime('now', '-7 days')",
        backend="postgresql",
    )
    assert "datetime(" not in sql.lower()
    assert "c.modified::timestamp >=" in sql
    assert "CAST(CAST('-7 days' AS text) AS interval)" in sql


def test_bare_datetime_column():
    sql = adapt_sql(
        "SELECT datetime(fetched_at) AS f FROM cache",
        backend="postgresql",
    )
    assert sql == "SELECT fetched_at::timestamp AS f FROM cache"


def test_date_dotted_column():
    sql = adapt_sql(
        "SELECT * FROM kev_deadlines k WHERE DATE(k.date_added) >= DATE('now', ?)",
        backend="postgresql",
    )
    assert "k.date_added::date" in sql


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


def test_kev_overdue_bound_date_compare():
    from db.dialect import prepare_query

    sql = (
        "EXISTS (SELECT 1 FROM kev_deadlines k WHERE k.cve_id = c.cve_id "
        "AND k.due_date IS NOT NULL AND k.due_date < ?)"
    )
    adapted, params = prepare_query(sql, ("2026-06-28",), backend="postgresql")
    assert "DATE(k.due_date)" not in adapted
    assert "date('now')" not in adapted
    assert "k.due_date < $1" in adapted
    assert params == ("2026-06-28",)


def test_snooze_until_datetime_compare():
    sql = adapt_sql(
        "datetime(snooze_until) > datetime('now')",
        backend="postgresql",
    )
    assert "datetime(snooze_until)" not in sql
    assert "snooze_until::timestamp >" in sql
