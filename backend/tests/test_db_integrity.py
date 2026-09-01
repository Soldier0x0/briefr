"""Tests for database integrity checks."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.integrity import run_integrity_check


class _FakeDb:
    def __init__(self, responses: dict[str, list]):
        self.responses = responses

    async def execute_fetchall(self, sql: str):
        for key, rows in self.responses.items():
            if key in sql:
                return rows
        return [{"cnt": 0}]


def test_postgres_integrity_fails_on_invalid_indexes(monkeypatch):
    monkeypatch.setattr("db.integrity.is_postgres", lambda: True)
    db = _FakeDb({
        "NOT i.indisvalid": [{"cnt": 2}],
        "NOT con.convalidated": [{"cnt": 0}],
        "child_table": [],
    })
    result = asyncio.run(run_integrity_check(db))
    assert result.ok is False
    assert result.backend == "postgresql"
    assert result.method == "pg_catalog"
    assert "invalid index" in result.message


def test_postgres_integrity_detects_fk_violations(monkeypatch):
    monkeypatch.setattr("db.integrity.is_postgres", lambda: True)
    db = _FakeDb({
        "NOT i.indisvalid": [{"cnt": 0}],
        "NOT con.convalidated": [{"cnt": 0}],
        "child_table": [{
            "child_table": "watchlist",
            "parent_table": "cves",
            "child_column": "cve_id",
            "parent_column": "cve_id",
        }],
        "LEFT JOIN": [{"cnt": 3}],
    })
    result = asyncio.run(run_integrity_check(db))
    assert result.ok is False
    assert result.foreign_keys_ok is False
    assert result.foreign_key_violations == 3


def test_postgres_integrity_ok_when_catalog_clean(monkeypatch):
    monkeypatch.setattr("db.integrity.is_postgres", lambda: True)
    db = _FakeDb({
        "NOT i.indisvalid": [{"cnt": 0}],
        "NOT con.convalidated": [{"cnt": 0}],
        "child_table": [],
    })
    result = asyncio.run(run_integrity_check(db))
    assert result.ok is True
    assert result.message == "ok"
