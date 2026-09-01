"""Tests for KEV enrichment fields (ransomware use, CWEs, vendor, name)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import _clean_iso_date, get_db, upsert_kev, upsert_kev_batch
from feeds.kev import parse_kev_catalog
from tests.conftest import run_db_test

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


def test_parse_kev_catalog_rejects_malformed_payload():
    assert parse_kev_catalog(None) == []
    assert parse_kev_catalog([]) == []
    assert parse_kev_catalog({"vulnerabilities": "not-a-list"}) == []
    assert parse_kev_catalog({"vulnerabilities": [None, "bad", 42]}) == []


def test_parse_kev_catalog_coerces_non_list_cwes():
    catalog = {
        "vulnerabilities": [
            {
                "cveID": "CVE-2020-0001",
                "product": "Widget",
                "shortDescription": "Test",
                "requiredAction": "Patch",
                "dueDate": "2020-01-01",
                "dateAdded": "2020-01-01",
                "cwes": "CWE-79",
            }
        ]
    }
    entries = parse_kev_catalog(catalog)
    assert len(entries) == 1
    assert entries[0]["cwes"] == []


def test_parse_kev_catalog_tolerates_missing_fields():
    entries = parse_kev_catalog(SAMPLE_CATALOG)
    log4j = entries[2]
    assert log4j["cveID"] == "CVE-2021-44228"
    assert log4j["vendorProject"] == ""
    assert log4j["vulnerabilityName"] == ""
    assert log4j["knownRansomwareCampaignUse"] == ""
    assert log4j["cwes"] == []


def test_clean_iso_date_accepts_valid_and_rejects_garbage():
    assert _clean_iso_date("2026-06-23") == "2026-06-23"
    assert _clean_iso_date("2026-06-23T12:00:00Z") == "2026-06-23T12:00:00Z"
    assert _clean_iso_date("") == ""
    assert _clean_iso_date(None) == ""
    assert _clean_iso_date("pending") == ""
    assert _clean_iso_date(123) == ""


def test_upsert_kev_sanitizes_null_and_garbage_dates():
    async def _run():
        db = await get_db()

        await upsert_kev(
            db,
            {
                "cveID": "CVE-2026-9999",
                "product": "Widget",
                "shortDescription": "Test",
                "requiredAction": "Patch",
                "dueDate": None,
                "dateAdded": "not-a-date",
            },
        )
        await db.commit()

        row = await db.execute_fetchall(
            "SELECT due_date, date_added FROM kev_deadlines WHERE cve_id = ?",
            ("CVE-2026-9999",),
        )
        assert dict(row[0]) == {"due_date": "", "date_added": ""}
        await db.close()

    run_db_test(_run())


def test_upsert_kev_stores_and_updates_enrichment_fields():
    async def _run():
        db = await get_db()

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

    run_db_test(_run())


def test_upsert_kev_batch_matches_per_row_results():
    """PR-P4: batched executemany writes the same rows as per-row upserts,
    skips entries without a cveID, and updates in place on re-sync."""
    async def _run():
        db = await get_db()

        entries = parse_kev_catalog(SAMPLE_CATALOG)
        count = await upsert_kev_batch(db, [*entries, {"product": "no-id"}])
        await db.commit()
        assert count == len(entries)

        rows = await db.execute_fetchall(
            "SELECT cve_id, vendor_project, cwes FROM kev_deadlines ORDER BY cve_id"
        )
        by_id = {r["cve_id"]: dict(r) for r in rows}
        assert len(by_id) == len(entries)
        assert by_id["CVE-2023-4966"]["vendor_project"] == "Citrix"
        assert json.loads(by_id["CVE-2023-4966"]["cwes"]) == ["CWE-119"]

        # Re-sync with a changed flag updates in place (no duplicate rows).
        updated = dict(entries[0])
        updated["knownRansomwareCampaignUse"] = "Known"
        await upsert_kev_batch(db, [updated])
        await db.commit()
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM kev_deadlines"
        )
        assert rows[0]["n"] == len(entries)
        flag = await db.execute_fetchall(
            "SELECT known_ransomware FROM kev_deadlines WHERE cve_id = ?",
            (entries[0]["cveID"],),
        )
        assert flag[0]["known_ransomware"] == "Known"
        await db.close()

    run_db_test(_run())


def test_upsert_kev_batch_empty_returns_zero():
    async def _run():
        db = await get_db()
        assert await upsert_kev_batch(db, []) == 0
        assert await upsert_kev_batch(db, [{"product": "no-id"}]) == 0
        await db.close()

    run_db_test(_run())
