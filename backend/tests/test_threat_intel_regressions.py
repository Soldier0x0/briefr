"""Regression assertions for the threat-intel release-gate invariants.

Runs on the default SQLite CI path with the Postgres-only classification seam
stubbed (same pattern as test_threat_intel_blocklist_fixes.py). Each test pins
one invariant the release plan refuses to loosen:

- IN-A: exact IOC evidence (raw_ioc / host_ioc) survives into the payload.
- IN-B: host-level suppression never suppresses an exact IOC match.
- IN-C: cpe_matches survives the catalog upsert verbatim.
- IN-D: OTX observed_at reaches blocklist freshness unchanged.
- IN-E: the export payload is deterministic across builds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blocklist.build as build_mod
import database
import db.blocklist as db_blocklist
from correlation.source_evidence import batch_source_evidence
from database import get_db, init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
from db.config import is_postgres
from db.cve import upsert_cves
from tests.conftest import run_db_test

_OTX_PULSE = [{
    "pulse_id": "pulse-reg",
    "pulse_name": "Regression pulse",
    "author": "analyst",
    "created_date": "2024-01-05",
    "adversary": "",
    "malware_families": [],
    "tags": [],
    "targeted_countries": [],
    "ioc_count": 1,
}]


async def _no_infra(db):
    return []


async def _seed_catalog_row(
    db,
    *,
    domain: str,
    raw_ioc: str = "",
    host_ioc: str = "",
    first_seen: str = "2024-06-01",
    source: str = "threatfox",
) -> None:
    await db.execute(
        """
        INSERT INTO ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
            threat_type, confidence_level, first_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            f"{source}-{domain}",
            "domain",
            domain,
            raw_ioc or domain,
            host_ioc,
            "redline",
            "botnet_cc",
            90,
            first_seen,
        ),
    )
    await db.commit()


def _patch_fetch_no_infra(monkeypatch):
    monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
    monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)


def test_exact_ioc_evidence_preserved_in_payload(tmp_path, monkeypatch):
    """IN-A: exact upstream IOC evidence must reach the export payload."""
    async def run():
        monkeypatch.setenv("DB_PATH", str(tmp_path / "reg-a.db"))
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "reg-a.db"))
        await init_db()
        db = await database.get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            raw_url = "https://malware.example/loader?token=abc123%2Fdef"
            await _seed_catalog_row(
                db,
                domain="malware.example",
                raw_ioc=raw_url,
                host_ioc="malware.example",
            )
            payload = await build_mod.build_blocklist(db)
            rec = next(
                r for r in payload["domains"] if r["domain"] == "malware.example"
            )
            evidence = rec["evidence"]
            assert evidence, "expected an evidence row"
            exact = evidence[0]
            assert exact["raw_ioc"] == raw_url, exact
            assert exact["ioc_value"] == "malware.example"
            assert exact["host_ioc"] == "malware.example"
            assert exact["source"] == "threatfox"
        finally:
            await db.close()

    run_db_test(run())


def test_host_level_suppression_does_not_suppress_exact_match(tmp_path, monkeypatch):
    """IN-B: suppress_host_level skips only the host_ioc join for a DOMAIN
    edge; an exact ioc_value URL match on the same row must survive."""
    async def run():
        monkeypatch.setenv("DB_PATH", str(tmp_path / "reg-b.db"))
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "reg-b.db"))
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc,
                    malware, threat_type, confidence_level, first_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "urlhaus", "urlh-1", "url",
                    "https://drive.google.com/research/tools",
                    "https://drive.google.com/research/tools",
                    "drive.google.com", None, None, 100, "2024-06-01",
                ),
            )
            await db.commit()

            edges = [
                ("DOMAIN", "drive.google.com"),
                ("URL", "https://drive.google.com/research/tools"),
            ]
            hits_with_suppress = await batch_source_evidence(
                db,
                edges,
                suppress_host_level=frozenset({"drive.google.com"}),
            )
            domain_key = ("DOMAIN", "drive.google.com")
            url_key = ("URL", "https://drive.google.com/research/tools")
            assert domain_key not in hits_with_suppress, (
                "host-level corroboration must be suppressed"
            )
            assert url_key in hits_with_suppress, (
                "exact URL match must survive host-level suppression"
            )
            assert hits_with_suppress[url_key][0]["source"] == "urlhaus"

            hits_without_suppress = await batch_source_evidence(db, edges)
            assert domain_key in hits_without_suppress, (
                "without suppression the host-level join must yield a hit"
            )
        finally:
            await db.close()

    run_db_test(run())


def test_cpe_matches_survive_catalog_upsert(tmp_path, monkeypatch):
    """IN-C: cpe_matches list must round-trip verbatim through the upsert
    (order and values), never being reset or reordered."""
    if not is_postgres():
        db_path = str(tmp_path / "reg-c.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)

    cpe = [
        {"vendor": "apache", "product": "http_server", "version_start_including": "2.4.0"},
        {"vendor": "nginx", "product": "nginx", "version": "1.20.0"},
    ]

    async def run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cves(db, [{
                "cve_id": "CVE-2024-9991", "description": "with cpes",
                "cpe_matches": cpe,
            }])
            await db.commit()
            q = "SELECT cpe_matches FROM cves WHERE cve_id = ?"
            if is_postgres():
                q = "SELECT cpe_matches FROM cves WHERE cve_id = $1"
            rows = await db.execute_fetchall(q, ("CVE-2024-9991",))
            assert rows and json.loads(rows[0]["cpe_matches"]) == cpe, (
                "cpe_matches must round-trip verbatim"
            )
            # A later upsert that omits cpe_matches must not wipe it.
            await upsert_cves(db, [{
                "cve_id": "CVE-2024-9991", "description": "no cpes",
            }])
            await db.commit()
            rows = await db.execute_fetchall(q, ("CVE-2024-9991",))
            assert json.loads(rows[0]["cpe_matches"]) == cpe, (
                "stored cpe_matches must survive an upsert that omits the field"
            )
        finally:
            await db.close()

    run_db_test(run())


def test_otx_observed_at_feeds_freshness_regression(tmp_path, monkeypatch):
    """IN-D: OTX observed_at feeds the blocklist evidence first_seen
    unchanged (no silent fallback to a fresh value)."""
    async def run():
        monkeypatch.setenv("DB_PATH", str(tmp_path / "reg-d.db"))
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "reg-d.db"))
        await init_db()
        db = await database.get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await replace_otx_cve_pulses(db, "CVE-2024-8899", _OTX_PULSE)
            await replace_otx_pulse_iocs(db, "pulse-reg", [{
                "ioc_type": "DOMAIN",
                "ioc_value": "reg-stale.example",
                "description": "C2",
                "observed_at": "2021-03-15T08:00:00Z",
            }])
            await _seed_catalog_row(db, domain="reg-stale.example")
            payload = await build_mod.build_blocklist(db)
            rec = next(
                r for r in payload["domains"] if r["domain"] == "reg-stale.example"
            )
            otx_row = next(
                e for e in rec["evidence"] if e.get("pulse_id")
            )
            assert otx_row["first_seen"] == "2021-03-15T08:00:00Z", (
                "OTX observed_at must map into evidence first_seen unchanged"
            )
        finally:
            await db.close()

    run_db_test(run())


def test_blocklist_payload_deterministic_between_builds(tmp_path, monkeypatch):
    """IN-E: two builds over identical data yield byte-identical payloads."""
    async def run():
        cache_dir = str(tmp_path / "reg-e")
        monkeypatch.setenv("DB_PATH", f"{cache_dir}.db")
        monkeypatch.setattr(database, "DB_PATH", f"{cache_dir}.db")
        await init_db()
        db = await database.get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            for domain in ("aa.example", "bb.example"):
                await _seed_catalog_row(
                    db, domain=domain, first_seen="2024-06-01"
                )
            first = json.dumps(await build_mod.build_blocklist(db), sort_keys=True)
            second = json.dumps(await build_mod.build_blocklist(db), sort_keys=True)
            assert first == second, "payload must be deterministic across builds"
            assert first.count('"domain"') >= 2
        finally:
            await db.close()

    run_db_test(run())