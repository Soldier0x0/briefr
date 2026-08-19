"""Tranco infra-sync: HTTP errors, circuit-open skip, expire superseded rows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blocklist.tranco_sync import fetch_tranco_domains, sync_tranco_infra_classifications
from db.blocklist import expire_superseded_tranco_hosts
from feeds.errors import FeedFetchError
from resilient_client import CircuitOpenError


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code = status_code
        self.content = content


class _FakeCursor:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _FakeInfraDb:
    def __init__(self, rows: list[dict]):
        self.rows = [dict(r) for r in rows]
        self.expired_ids: list[int] = []

    async def execute_fetchall(self, sql, params=()):
        if "provenance LIKE 'tranco:%'" in sql:
            return [
                {"id": r["id"], "host": r["host"]}
                for r in self.rows
                if r.get("enabled") == 1 and str(r.get("provenance", "")).startswith("tranco:")
            ]
        return []

    async def execute(self, sql, params=()):
        if "SET enabled = 0" in sql:
            ids = [int(x) for x in params[1:]]
            self.expired_ids.extend(ids)
            for row in self.rows:
                if row["id"] in ids:
                    row["enabled"] = 0
            return _FakeCursor(len(ids))
        return _FakeCursor(0)


def test_fetch_tranco_http_5xx_raises_feed_error(monkeypatch):
    async def fake_request(*args, **kwargs):
        return _FakeResponse(503)

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr("blocklist.tranco_sync.resilient_request", fake_request)
    monkeypatch.setattr("blocklist.tranco_sync.record_api_call", fake_record)

    with pytest.raises(FeedFetchError, match="HTTP 503"):
        asyncio.run(fetch_tranco_domains())


def test_fetch_tranco_circuit_open_skips(monkeypatch):
    async def fake_request(*args, **kwargs):
        raise CircuitOpenError("tranco", 0)

    monkeypatch.setattr("blocklist.tranco_sync.resilient_request", fake_request)

    list_date, domains = asyncio.run(fetch_tranco_domains())
    assert list_date == ""
    assert domains == []


def test_expire_superseded_tranco_skips_operator_rows():
    db = _FakeInfraDb(
        [
            {"id": 1, "host": "old.example", "enabled": 1, "provenance": "tranco:2026-01-01"},
            {"id": 2, "host": "keep.example", "enabled": 1, "provenance": "tranco:2026-01-01"},
            {"id": 3, "host": "operator.example", "enabled": 1, "provenance": "operator"},
        ]
    )

    expired = asyncio.run(expire_superseded_tranco_hosts(db, ["keep.example"]))
    assert expired == 1
    assert db.expired_ids == [1]
    by_id = {r["id"]: r for r in db.rows}
    assert by_id[1]["enabled"] == 0
    assert by_id[2]["enabled"] == 1
    assert by_id[3]["enabled"] == 1


def test_sync_skips_expire_on_empty_fetch(monkeypatch):
    async def fake_fetch():
        return "2026-08-01", []

    called = []

    async def fake_expire(db, hosts):
        called.append(hosts)
        return 0

    monkeypatch.setattr("blocklist.tranco_sync.fetch_tranco_domains", fake_fetch)
    monkeypatch.setattr("blocklist.tranco_sync.expire_superseded_tranco_hosts", fake_expire)

    written = asyncio.run(sync_tranco_infra_classifications(object()))
    assert written == 0
    assert called == []
