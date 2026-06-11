"""Tests for CIRCL (vulnerability.circl.lu) migration and OSV by-ID lookup."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_feed_cache, init_db
from feeds import extended, osv

CVE5_RECORD = {
    "dataType": "CVE_RECORD",
    "dataVersion": "5.1",
    "cveMetadata": {"cveId": "CVE-2021-44228", "state": "PUBLISHED"},
    "containers": {
        "cna": {
            "references": [
                {"url": "https://logging.apache.org/log4j/2.x/security.html"},
                {"url": "http://www.openwall.com/lists/oss-security/2021/12/10/1"},
            ],
            "impacts": [{"capecId": "CAPEC-137", "descriptions": []}],
        },
        "adp": [
            {
                "references": [{"url": "https://example.org/adp-ref"}],
            }
        ],
    },
}

OSV_RECORD = {
    "id": "CVE-2021-44228",
    "summary": "Log4j JNDI RCE",
    "modified": "2024-01-01T00:00:00Z",
    "affected": [
        {
            "package": {"ecosystem": "Maven", "name": "org.apache.logging.log4j:log4j-core"},
            "ranges": [
                {"events": [{"introduced": "2.0"}, {"fixed": "2.15.0"}]}
            ],
        }
    ],
}


def test_normalize_circl_record_extracts_refs_and_capec():
    norm = extended._normalize_circl_record(CVE5_RECORD)
    assert "https://logging.apache.org/log4j/2.x/security.html" in norm["references"]
    assert "https://example.org/adp-ref" in norm["references"]
    assert norm["capec"] == ["CAPEC-137"]


def test_merge_accepts_normalized_record():
    cve = {"cve_id": "CVE-2021-44228", "source_urls": [], "cwe_ids": []}
    merged = extended.merge_circl_into_cve(cve, extended._normalize_circl_record(CVE5_RECORD))
    assert merged["capec_ids"] == ["CAPEC-137"]
    assert merged["circl"]["extra_reference_count"] == 3


def test_circl_failure_is_negative_cached(tmp_path, monkeypatch):
    db_path = tmp_path / "circl.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def run():
        await init_db()
        from database import get_db

        fetch_mock = AsyncMock(return_value=None)  # transient failure
        monkeypatch.setattr(extended, "fetch_circl_cve", fetch_mock)

        db = await get_db()
        try:
            assert await extended.load_circl_for_cve(db, "CVE-2024-0001") is None
            await db.commit()
            # Second call must hit the miss cache — no new fetch.
            assert await extended.load_circl_for_cve(db, "CVE-2024-0001") is None
            assert fetch_mock.await_count == 1
            miss = await get_feed_cache(db, "circl_miss:CVE-2024-0001", max_age_hours=24)
            assert miss == {"miss": True}
        finally:
            await db.close()

    asyncio.run(run())


def test_circl_success_and_empty_results_are_cached(tmp_path, monkeypatch):
    db_path = tmp_path / "circl2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def run():
        await init_db()
        from database import get_db

        normalized = extended._normalize_circl_record(CVE5_RECORD)
        fetch_mock = AsyncMock(side_effect=[normalized, {}])
        monkeypatch.setattr(extended, "fetch_circl_cve", fetch_mock)

        db = await get_db()
        try:
            got = await extended.load_circl_for_cve(db, "CVE-2021-44228")
            assert got["capec"] == ["CAPEC-137"]
            await db.commit()
            # Cached — no second fetch for the same ID.
            again = await extended.load_circl_for_cve(db, "CVE-2021-44228")
            assert again["capec"] == ["CAPEC-137"]

            # Empty result ({} = CIRCL has nothing) is cached as a success.
            assert await extended.load_circl_for_cve(db, "CVE-2099-9999") is None
            await db.commit()
            assert await extended.load_circl_for_cve(db, "CVE-2099-9999") is None
            assert fetch_mock.await_count == 2
        finally:
            await db.close()

    asyncio.run(run())


def test_osv_parses_single_vuln_record(monkeypatch):
    class FakeResponse:
        def json(self):
            return OSV_RECORD

    monkeypatch.setattr(osv, "resilient_get", AsyncMock(return_value=FakeResponse()))
    monkeypatch.setattr(osv, "record_api_call", AsyncMock())

    results = asyncio.run(osv.fetch_osv_by_cve("CVE-2021-44228"))
    assert len(results) == 1
    assert results[0]["osv_id"] == "CVE-2021-44228"
    eco = results[0]["ecosystems"][0]
    assert eco["ecosystem"] == "Maven"
    assert {"fixed": "2.15.0"} in eco["packages"][0]["versions"]


def test_osv_follows_alias_when_cve_record_has_no_packages(monkeypatch):
    cve_record = {
        "id": "CVE-2021-44228",
        "aliases": ["GHSA-jfh8-c2jp-5v3q"],
        # GIT-only ranges with no package info — the real-world CVE shape.
        "affected": [{"ranges": [{"type": "GIT", "events": []}]}],
    }
    alias_record = dict(OSV_RECORD, id="GHSA-jfh8-c2jp-5v3q")

    async def fake_fetch(vuln_id):
        return cve_record if vuln_id.startswith("CVE-") else alias_record

    monkeypatch.setattr(osv, "_fetch_osv_record", fake_fetch)

    results = asyncio.run(osv.fetch_osv_by_cve("CVE-2021-44228"))
    assert len(results) == 1
    assert results[0]["osv_id"] == "GHSA-jfh8-c2jp-5v3q"
    assert results[0]["ecosystems"][0]["ecosystem"] == "Maven"
