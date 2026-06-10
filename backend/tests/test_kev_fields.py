"""Tests for KEV enrichment fields (ransomware use, CWEs, vendor, name)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite

from database import upsert_kev
from feeds.kev import parse_kev_catalog

SAMPLE_CATALOG = {
    "title": "CISA Catalog of Known Exploited Vulnerabilities",
    "catalogVersion": "2026.06.09",
    "vulnerabilities": [
        {
            "cveID": "CVE-2026-11645",
            "vendorProject": "Google",
            "product": "Chromium V8",
            "vulnerabilityName": "Google Chromium V8 Out-of-Bounds Read and Write Vulnerability",
            "dateAdded": "2026-06-09",
            "shortDescription": "Out-of-bounds read and write in V8.",
            "requiredAction": "Apply mitigations per vendor instructions.",
            "dueDate": "2026-06-23",
            "knownRansomwareCampaignUse": "Unknown",
            "cwes": ["CWE-787", "CWE-125"],
        },
        {
            "cveID": "CVE-2023-4966",
            "vendorProject": "Citrix",
            "product": "NetScaler ADC",
            "vulnerabilityName": "Citrix NetScaler Buffer Overflow (Citrix Bleed)",
            "dateAdded": "2023-10-18",
            "shortDescription": "Session token leakage.",
            "requiredAction": "Apply updates per vendor instructions.",
            "dueDate": "2023-11-08",
            "knownRansomwareCampaignUse": "Known",
            "cwes": ["CWE-119"],
        },
        {
            # Older catalog entries may omit the newer fields entirely.
            "cveID": "CVE-2021-44228",
            "product": "Log4j",
            "shortDescription": "JNDI injection RCE.",
            "requiredAction": "Patch.",
            "dueDate": "2021-12-24",
            "dateAdded": "2021-12-10",
        },
    ],
}


def _kev_table_sql() -> str:
    return """
        CREATE TABLE kev_deadlines (
            cve_id TEXT PRIMARY KEY,
            product TEXT,
            short_description TEXT,
            required_action TEXT,
            due_date TEXT,
            date_added TEXT,
            vendor_project TEXT DEFAULT '',
            vulnerability_name TEXT DEFAULT '',
            known_ransomware TEXT DEFAULT '',
            cwes TEXT DEFAULT '[]',
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """


def test_parse_kev_catalog_keeps_enrichment_fields():
    entries = parse_kev_catalog(SAMPLE_CATALOG)
    assert len(entries) == 3

    chromium = entries[0]
    assert chromium["cveID"] == "CVE-2026-11645"
    assert chromium["vendorProject"] == "Google"
    assert chromium["vulnerabilityName"].startswith("Google Chromium V8")
    assert chromium["knownRansomwareCampaignUse"] == "Unknown"
    assert chromium["cwes"] == ["CWE-787", "CWE-125"]

    citrix = entries[1]
    assert citrix["knownRansomwareCampaignUse"] == "Known"
    assert citrix["cwes"] == ["CWE-119"]


def test_parse_kev_catalog_tolerates_missing_fields():
    entries = parse_kev_catalog(SAMPLE_CATALOG)
    log4j = entries[2]
    assert log4j["cveID"] == "CVE-2021-44228"
    assert log4j["vendorProject"] == ""
    assert log4j["vulnerabilityName"] == ""
    assert log4j["knownRansomwareCampaignUse"] == ""
    assert log4j["cwes"] == []


def test_upsert_kev_stores_and_updates_enrichment_fields():
    async def _run():
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await db.execute(_kev_table_sql())

        entries = parse_kev_catalog(SAMPLE_CATALOG)
        for entry in entries:
            await upsert_kev(db, entry)
        await db.commit()

        rows = await db.execute_fetchall(
            """
            SELECT cve_id, vendor_project, vulnerability_name,
                   known_ransomware, cwes
            FROM kev_deadlines ORDER BY cve_id
            """
        )
        by_id = {r["cve_id"]: dict(r) for r in rows}

        citrix = by_id["CVE-2023-4966"]
        assert citrix["vendor_project"] == "Citrix"
        assert citrix["known_ransomware"] == "Known"
        assert json.loads(citrix["cwes"]) == ["CWE-119"]

        log4j = by_id["CVE-2021-44228"]
        assert log4j["known_ransomware"] == ""
        assert json.loads(log4j["cwes"]) == []

        # Re-sync with a changed ransomware flag must update in place.
        updated = dict(parse_kev_catalog(SAMPLE_CATALOG)[0])
        updated["knownRansomwareCampaignUse"] = "Known"
        await upsert_kev(db, updated)
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT known_ransomware FROM kev_deadlines WHERE cve_id = ?",
            ("CVE-2026-11645",),
        )
        assert rows[0]["known_ransomware"] == "Known"
        await db.close()

    asyncio.run(_run())
