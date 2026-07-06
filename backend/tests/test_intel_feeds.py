"""Tests for CISA Vulnrichment and cvelistV5 feed modules."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as db_module
import resilient_client
from feeds.cve_record_v5 import (
    cvelistv5_repo_path,
    merge_additive_cve_fields,
    parse_cvelistv5_record,
    parse_vulnrichment_record,
    vulnrichment_repo_path,
)
from feeds.cvelistv5 import SYNC_STATE_KEY, fetch_cvelistv5_delta
from feeds.vulnrichment import fetch_vulnrichment_enrichments
from scheduler import run_cvelistv5_sync, run_vulnrichment_sync

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_repo_path_helpers():
    assert vulnrichment_repo_path("CVE-2024-0043") == "2024/0xxx/CVE-2024-0043.json"
    assert cvelistv5_repo_path("CVE-2026-0005") == "cves/2026/0xxx/CVE-2026-0005.json"


def test_parse_vulnrichment_record_fixture():
    record = _load("vulnrichment_cve_2024_0043.json")
    parsed = parse_vulnrichment_record(record)
    assert parsed is not None
    assert parsed["cve_id"] == "CVE-2024-0043"
    assert parsed["cvss_score"] == 7.8
    assert parsed["severity"] == "HIGH"
    assert "CWE-863" in parsed["cwe_ids"]
    assert "google:android" in parsed["affected_products"]


def test_parse_cvelistv5_prefers_cna_over_adp():
    record = _load("cvelistv5_cve_2026_0005.json")
    parsed = parse_cvelistv5_record(record)
    assert parsed is not None
    assert parsed["cve_id"] == "CVE-2026-0005"
    assert parsed["cvss_score"] == 6.5
    assert parsed["severity"] == "MEDIUM"
    assert "CWE-200" in parsed["cwe_ids"]
    assert "abacus:erp" in parsed["affected_products"]
    assert "Abacus ERP" in parsed["description"]


def test_merge_additive_does_not_downgrade_cvss():
    existing = {
        "cve_id": "CVE-2024-0001",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "cwe_ids": ["CWE-79"],
        "description": "NVD analyzed",
        "affected_products": ["vendor:product"],
    }
    incoming = {
        "cve_id": "CVE-2024-0001",
        "cvss_score": 5.0,
        "severity": "MEDIUM",
        "cwe_ids": ["CWE-200"],
        "description": "CISA text",
        "affected_products": ["other:thing"],
    }
    changes = merge_additive_cve_fields(existing, incoming)
    assert changes is not None
    assert "cvss_score" not in changes
    assert "severity" not in changes
    assert "description" not in changes
    assert set(changes["cwe_ids"]) == {"CWE-79", "CWE-200"}
    assert set(changes["affected_products"]) == {"vendor:product", "other:thing"}


def test_parse_cvelistv5_tolerates_malformed_field_types():
    record = {
        "cveMetadata": {"cveId": "CVE-2024-9999", "datePublished": "", "dateUpdated": ""},
        "containers": {
            "cna": {
                "descriptions": [{"lang": "en", "value": 12345}],
                "metrics": [
                    {
                        "cvssV3_1": {
                            "baseScore": 5.0,
                            "baseSeverity": ["HIGH"],
                        }
                    }
                ],
                "problemTypes": [
                    {
                        "descriptions": [
                            {"cweId": 863, "description": ["CWE-863 Incorrect Authorization"]},
                            {"description": "CWE-200 Exposure"},
                        ]
                    }
                ],
                "affected": [{"vendor": 1, "product": 2}, {"vendor": "acme", "product": "widget"}],
            }
        },
    }
    parsed = parse_cvelistv5_record(record)
    assert parsed is not None
    assert parsed["cve_id"] == "CVE-2024-9999"
    assert parsed["description"] == ""
    assert parsed["severity"] == "UNKNOWN"
    assert parsed["cwe_ids"] == ["CWE-200"]
    assert parsed["affected_products"] == ["acme:widget"]


def test_merge_additive_fills_gaps():
    existing = {
        "cve_id": "CVE-2024-0002",
        "cvss_score": None,
        "severity": "UNKNOWN",
        "cwe_ids": [],
        "description": "",
        "affected_products": [],
    }
    incoming = {
        "cve_id": "CVE-2024-0002",
        "cvss_score": 7.8,
        "severity": "HIGH",
        "cwe_ids": ["CWE-863"],
        "description": "Gap fill",
        "affected_products": ["google:android"],
    }
    changes = merge_additive_cve_fields(existing, incoming)
    assert changes["cvss_score"] == 7.8
    assert changes["severity"] == "HIGH"
    assert changes["description"] == "Gap fill"


@pytest.fixture
def mock_transport():
    tree = _load("vulnrichment_tree_response.json")
    cve_record = _load("vulnrichment_cve_2024_0043.json")
    compare = _load("cvelistv5_compare_response.json")
    cvelist_record = _load("cvelistv5_cve_2026_0005.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/cisagov/vulnrichment/git/trees/develop"):
            return httpx.Response(200, json=tree)
        if path.endswith("/CVE-2024-0043.json") and "vulnrichment" in str(request.url):
            return httpx.Response(200, json=cve_record)
        if path.endswith("/commits/main") and "cvelistV5" in path:
            return httpx.Response(200, json={"sha": "headsha111111"})
        if "/compare/" in path and "cvelistV5" in path:
            return httpx.Response(200, json=compare)
        if path.endswith("/CVE-2026-0005.json") and "cvelistV5" in str(request.url):
            return httpx.Response(200, json=cvelist_record)
        if path.endswith("/CVE-2026-0006.json") and "cvelistV5" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


@pytest.fixture(autouse=True)
def reset_health(monkeypatch, mock_transport):
    resilient_client.reset_feed_health()
    monkeypatch.setattr(resilient_client, "_client", mock_transport)
    yield
    resilient_client.reset_feed_health()


def test_fetch_vulnrichment_enrichments_targeted():
    async def run():
        enrichments = await fetch_vulnrichment_enrichments({"CVE-2024-0043"})
        assert len(enrichments) == 1
        assert enrichments[0]["cve_id"] == "CVE-2024-0043"
        health = resilient_client.get_feed_health()
        assert "vulnrichment" in health
        assert health["vulnrichment"]["circuit_open"] is False

    asyncio.run(run())


def test_fetch_cvelistv5_delta_advances_watermark():
    async def run():
        records, rejected, head, advance = await fetch_cvelistv5_delta("basesha000000")
        assert advance is True
        assert head == "headsha111111"
        assert rejected == []
        assert len(records) == 1
        assert records[0]["cve_id"] == "CVE-2026-0005"
        health = resilient_client.get_feed_health()
        assert "cvelistv5" in health

    asyncio.run(run())


def test_parse_vulnrichment_record_extracts_ssvc():
    record = {
        "cveMetadata": {"cveId": "CVE-2024-9999", "state": "PUBLISHED"},
        "containers": {
            "adp": [
                {
                    "title": "CISA ADP Vulnrichment",
                    "metrics": [
                        {
                            "other": {
                                "type": "ssvc",
                                "content": {
                                    "role": "CISA-Coordinator",
                                    "version": "2.0.3",
                                    "options": [
                                        {"Exploitation": "active"},
                                        {"Automatable": "yes"},
                                        {"Technical Impact": "total"},
                                        {"Decision": "Act"},
                                    ],
                                },
                            }
                        }
                    ],
                }
            ],
        },
    }
    parsed = parse_vulnrichment_record(record)
    assert parsed is not None
    assert parsed["ssvc"]["decisions"]["Exploitation"] == "active"
    assert parsed["ssvc"]["decisions"]["Decision"] == "Act"


def test_parse_vulnrichment_record_ssvc_includes_computed_with_options():
    record = {
        "cveMetadata": {"cveId": "CVE-2024-9998", "state": "PUBLISHED"},
        "containers": {
            "adp": [
                {
                    "title": "CISA ADP Vulnrichment",
                    "metrics": [
                        {
                            "other": {
                                "type": "ssvc",
                                "content": {
                                    "options": [{"Exploitation": "active"}],
                                    "computed": "Exploitation:active/Automatable:yes/Decision:Act",
                                },
                            }
                        }
                    ],
                }
            ],
        },
    }
    parsed = parse_vulnrichment_record(record)
    assert parsed is not None
    assert parsed["ssvc"]["decisions"]["Exploitation"] == "active"
    assert parsed["ssvc"]["decisions"]["computed"] == "Exploitation:active/Automatable:yes/Decision:Act"


def test_apply_additive_enrichment_in_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "intel_feeds.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db_module.upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-0043",
                    "description": "",
                    "cvss_score": None,
                    "severity": "UNKNOWN",
                    "cwe_ids": [],
                    "affected_products": [],
                },
            )
            await db.commit()

            enrichment = parse_vulnrichment_record(_load("vulnrichment_cve_2024_0043.json"))
            updated = await db_module.apply_additive_cve_enrichments(db, [enrichment])
            await db.commit()
            assert updated == 1

            row = await db.execute_fetchall(
                "SELECT cvss_score, severity, cwe_ids FROM cves WHERE cve_id = ?",
                ("CVE-2024-0043",),
            )
            assert row[0]["cvss_score"] == 7.8
            assert row[0]["severity"] == "HIGH"
            assert "CWE-863" in json.loads(row[0]["cwe_ids"])
        finally:
            await db.close()

    asyncio.run(run())


def test_apply_additive_stores_ssvc_in_feed_cache(tmp_path, monkeypatch):
    db_file = str(tmp_path / "intel_ssvc.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db_module.upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-9999",
                    "description": "filled",
                    "cvss_score": 8.0,
                    "severity": "HIGH",
                    "cwe_ids": ["CWE-79"],
                    "affected_products": ["vendor:product"],
                },
            )
            await db.commit()

            enrichment = parse_vulnrichment_record(
                {
                    "cveMetadata": {"cveId": "CVE-2024-9999", "state": "PUBLISHED"},
                    "containers": {
                        "adp": [
                            {
                                "title": "CISA ADP Vulnrichment",
                                "metrics": [
                                    {
                                        "other": {
                                            "type": "ssvc",
                                            "content": {
                                                "options": [{"Decision": "Track"}],
                                            },
                                        }
                                    }
                                ],
                            }
                        ],
                    },
                }
            )
            updated = await db_module.apply_additive_cve_enrichments(db, [enrichment])
            await db.commit()
            assert updated == 1

            cached = await db_module.get_feed_cache(db, "ssvc:CVE-2024-9999", max_age_hours=1)
            assert cached["decisions"]["Decision"] == "Track"
        finally:
            await db.close()

    asyncio.run(run())


def test_scheduler_cvelistv5_sets_sync_state(tmp_path, monkeypatch):
    db_file = str(tmp_path / "scheduler_cvelist.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    async def run():
        await db_module.init_db()
        await run_cvelistv5_sync()
        db = await db_module.get_db()
        try:
            marker = await db_module.get_sync_state_value(db, SYNC_STATE_KEY)
            assert marker == "headsha111111"
        finally:
            await db.close()

    asyncio.run(run())


def test_scheduler_vulnrichment_updates_gap_cve(tmp_path, monkeypatch):
    db_file = str(tmp_path / "scheduler_vuln.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db_module.upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-0043",
                    "description": "",
                    "cvss_score": None,
                    "severity": "UNKNOWN",
                    "cwe_ids": [],
                },
            )
            await db.commit()
        finally:
            await db.close()

        await run_vulnrichment_sync()

        db = await db_module.get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT cvss_score, severity FROM cves WHERE cve_id = ?",
                ("CVE-2024-0043",),
            )
            assert row[0]["cvss_score"] == 7.8
            assert row[0]["severity"] == "HIGH"
        finally:
            await db.close()

    asyncio.run(run())
