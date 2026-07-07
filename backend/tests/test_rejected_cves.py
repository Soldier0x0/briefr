"""Rejected / withdrawn CVE filtering on NVD and cvelistV5 ingest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database as db_module
from feeds.cve_record_v5 import is_cve_record_rejected, parse_cvelistv5_record
from feeds.nvd import _is_nvd_cve_rejected, _nvd_rejected_cve_id, _parse_cve_item

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_nvd_rejected_item_skipped():
    item = {
        "cve": {
            "id": "CVE-2026-54102",
            "vulnStatus": "Rejected",
            "descriptions": [
                {"lang": "en", "value": "Rejected reason: Reserved but no longer needed."}
            ],
            "published": "2026-06-12T14:16:33.330",
            "lastModified": "2026-06-12T14:16:33.330",
        }
    }
    assert _is_nvd_cve_rejected(item["cve"]) is True
    assert _nvd_rejected_cve_id(item) == "CVE-2026-54102"
    assert _parse_cve_item(item) is None


def test_nvd_published_item_parsed():
    item = {
        "cve": {
            "id": "CVE-2024-0001",
            "vulnStatus": "Analyzed",
            "descriptions": [{"lang": "en", "value": "Example vulnerability."}],
            "published": "2024-01-01T00:00:00.000",
            "lastModified": "2024-01-02T00:00:00.000",
            "metrics": {},
            "references": [],
            "weaknesses": [],
        }
    }
    parsed = _parse_cve_item(item)
    assert parsed is not None
    assert parsed["cve_id"] == "CVE-2024-0001"
    assert parsed["description"] == "Example vulnerability."


def test_cvelist_rejected_record_skipped():
    record = _load("cvelistv5_cve_2026_54102_rejected.json")
    assert is_cve_record_rejected(record) == "CVE-2026-54102"
    assert parse_cvelistv5_record(record) is None


def test_delete_cves_and_legacy_purge(tmp_path, monkeypatch):
    db_file = str(tmp_path / "rejected.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db_module.upsert_cve(
                db,
                {
                    "cve_id": "CVE-2026-54102",
                    "description": "Rejected reason: Reserved but no longer needed.",
                    "severity": "UNKNOWN",
                },
            )
            await db_module.upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-0001",
                    "description": "Real vulnerability",
                    "severity": "HIGH",
                },
            )
            await db.commit()

            legacy = await db_module.purge_legacy_rejected_cves(db)
            assert legacy == 1

            purged = await db_module.delete_cves_by_ids(db, ["CVE-2026-54101"])
            assert purged == 0

            rows = await db.execute_fetchall("SELECT cve_id FROM cves ORDER BY cve_id")
            assert [r["cve_id"] for r in rows] == ["CVE-2024-0001"]
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())
