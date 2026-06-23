"""Tests for SQLite -> PostgreSQL migration helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migration.sqlite_to_postgres import (
    SERIAL_ID_TABLES,
    TABLE_ORDER,
    _intersect_columns,
)


def test_table_order_includes_auth_and_webhooks():
    assert "users" in TABLE_ORDER
    assert "sessions" in TABLE_ORDER
    assert TABLE_ORDER.index("users") < TABLE_ORDER.index("sessions")
    assert "webhook_destinations" in TABLE_ORDER
    assert "webhook_delivery_log" in TABLE_ORDER
    assert "otx_pulses" in TABLE_ORDER
    assert "correlation_suppressions" in TABLE_ORDER


def test_serial_id_tables_cover_auth_and_webhooks():
    for table in ("users", "sessions", "webhook_delivery_log", "correlation_suppressions"):
        assert table in SERIAL_ID_TABLES


def test_intersect_columns_case_insensitive():
    sqlite_cols = ["cve_id", "CVSS_Score", "description"]
    pg_cols = ["cve_id", "cvss_score", "description", "extra"]
    sqlite_select, pg_insert = _intersect_columns(sqlite_cols, pg_cols)
    assert sqlite_select == ["cve_id", "CVSS_Score", "description"]
    assert pg_insert == ["cve_id", "cvss_score", "description"]
