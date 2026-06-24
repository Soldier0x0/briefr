"""Tests for /api/stats/timeline date normalization (Postgres asyncpg date objects)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.cves import _timeline_date_key


def test_timeline_date_key_from_date_object():
    assert _timeline_date_key(date(2026, 6, 24)) == "2026-06-24"


def test_timeline_date_key_from_string():
    assert _timeline_date_key("2026-06-24T12:00:00Z") == "2026-06-24"


def test_timeline_by_date_lookup_uses_iso_strings():
    """Postgres returns date objects; timeline fill must key by isoformat strings."""
    today = date(2026, 6, 24)
    yesterday = date(2026, 6, 23)
    by_date = {}
    for row_date, count in ((yesterday, 5), (today, 3)):
        key = _timeline_date_key(row_date)
        by_date[key] = {"date": key, "count": count}
    assert by_date[yesterday.isoformat()]["count"] == 5
    assert by_date[today.isoformat()]["count"] == 3
