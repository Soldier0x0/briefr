"""Regression tests for the approved Threat-Intel blocklist HIGH fixes.

Covers:
- B1: OTX observed_at is used by the blocklist freshness path (stale IOCs
      decay rather than silently falling back to a fresh value).
- B2: exact IOC evidence (raw_ioc / host_ioc / ioc_value / ioc_type / source
      / ref_id) survives in the internal evidence representation, the TXT
      export stays one-domain-per-line, and the JSON export preserves
      sufficient provenance.

The blocklist build is Postgres-oriented (infra_classifications is a
Postgres-only app-schema table), so the pure evidence/freshness paths are
exercised on SQLite with classification stubbed out.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blocklist.build as build_mod
import database
import db.blocklist as db_blocklist
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
from tests.conftest import run_db_test

_OTX_PULSE = [{
    "pulse_id": "pulse-fix",
    "pulse_name": "Fix regression",
    "author": "analyst",
    "created_date": "2024-01-05",
    "adversary": "",
    "malware_families": [],
    "tags": [],
    "targeted_countries": [],
    "ioc_count": 1,
}]


async def _seed_catalog_row(
    db,
    *,
    domain: str,
    raw_ioc: str = "",
    host_ioc: str = "",
    first_seen: str = "2024-06-01",
) -> None:
    await db.execute(
        """
        INSERT INTO ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
            threat_type, confidence_level, first_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "threatfox",
            f"tf-{domain}",
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


async def _no_infra(db):
    return []


def test_otx_observed_at_feeds_blocklist_freshness(tmp_path, monkeypatch):
    """A stale OTX IOC decays in the blocklist confidence path (not a silent
    fallback to a fresh/default value)."""
    async def run():
        db_path = str(tmp_path / "b1.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            # OTX IOC observed a long time ago; ThreatFox backs the same domain.
            await replace_otx_cve_pulses(db, "CVE-2024-6001", _OTX_PULSE)
            await replace_otx_pulse_iocs(db, "pulse-fix", [{
                "ioc_type": "DOMAIN",
                "ioc_value": "stale.example",
                "description": "C2",
                "observed_at": "2020-01-01T00:00:00Z",
            }])
            await _seed_catalog_row(db, domain="stale.example", first_seen="2020-01-02")

            payload = await build_mod.build_blocklist(db)
            rec = next(
                r for r in payload["domains"] if r["domain"] == "stale.example"
            )
            assert rec["evidence"], "expected per-row evidence"
            otx_row = next(
                e for e in rec["evidence"] if e.get("pulse_id")
            )
            assert otx_row["first_seen"] == "2020-01-01T00:00:00Z", (
                "OTX observed_at must be mapped into the evidence row"
            )

            factors = rec.get("confidence_factors") or []
            freshness = next(
                (f for f in factors if f["factor"] == "freshness"), None
            )
            assert freshness is not None, "expected a freshness factor"
            assert freshness.get("freshness_fallback") is not True, (
                "stale OTX IOC must receive real decay, not the fallback"
            )
            assert freshness["value"] < 1.0, (
                f"expected decayed freshness, got {freshness['value']}"
            )
        finally:
            await db.close()

    run_db_test(run())


def test_otx_observed_at_absent_falls_back(tmp_path, monkeypatch):
    """Without an observed_at the path still degrades safely (no crash, and
    the fallback is explicitly flagged rather than silently treated as fresh
    data that overstates confidence)."""
    async def run():
        db_path = str(tmp_path / "b1b.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            await replace_otx_cve_pulses(db, "CVE-2024-6002", _OTX_PULSE)
            await replace_otx_pulse_iocs(db, "pulse-fix", [{
                "ioc_type": "DOMAIN",
                "ioc_value": "no-timestamp.example",
                "description": "C2",
            }])
            await _seed_catalog_row(db, domain="no-timestamp.example")

            payload = await build_mod.build_blocklist(db)
            rec = next(
                r for r in payload["domains"] if r["domain"] == "no-timestamp.example"
            )
            freshness = next(
                (f for f in rec.get("confidence_factors") or [] if f["factor"] == "freshness"),
                None,
            )
            # A missing observed_at must not crash the pipeline; the freshness
            # factor is either absent or flagged as a fallback.
            assert freshness is None or freshness.get("freshness_fallback") is True
        finally:
            await db.close()

    run_db_test(run())


def test_exact_ioc_distinct_from_host_in_evidence(tmp_path, monkeypatch):
    """Exact malicious URLs on shared infrastructure stay distinguishable from
    their host in the evidence representation."""
    async def run():
        db_path = str(tmp_path / "b2.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            for url, host in [
                ("https://drive.google.com/uc?export=download&id=ABC", "drive.google.com"),
                ("https://t.me/example", "t.me"),
                ("https://steamcommunity.com/profiles/123", "steamcommunity.com"),
            ]:
                await _seed_catalog_row(
                    db,
                    domain=host,
                    raw_ioc=url,
                    host_ioc=host,
                    first_seen="2024-06-01",
                )

            payload = await build_mod.build_blocklist(db)
            by_domain = {r["domain"]: r for r in payload["domains"]}
            for host in ("drive.google.com", "t.me", "steamcommunity.com"):
                assert host in by_domain, f"{host} missing from candidates"
                evidence = by_domain[host]["evidence"]
                assert evidence, f"{host}: no evidence rows"
                exact = evidence[0]
                assert exact["raw_ioc"].startswith("https://"), exact
                assert exact["ioc_type"] == "domain"
                assert exact["source"] == "threatfox"
                assert exact["ref_id"]
                assert exact["host_ioc"] == host
                # The exact IOC stays available and distinct from the host.
                assert exact["ioc_value"] == host
                assert exact["raw_ioc"] != host

            assert payload["meta"]["eligible_count"] == 3
        finally:
            await db.close()

    run_db_test(run())


def test_txt_export_is_single_domain_per_line(tmp_path, monkeypatch):
    from blocklist.serialize import to_txt

    async def run():
        db_path = str(tmp_path / "b2txt.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            await _seed_catalog_row(db, domain="drive.google.com", raw_ioc="https://drive.google.com/uc?export=download&id=ABC", host_ioc="drive.google.com")
            await _seed_catalog_row(db, domain="t.me", raw_ioc="https://t.me/example", host_ioc="t.me")

            payload = await build_mod.build_blocklist(db)
            text = to_txt(payload)
            body_lines = [
                line for line in text.splitlines()
                if line and not line.startswith("#")
            ]
            assert body_lines == ["drive.google.com", "t.me"], (
                "TXT must be one canonical domain per line, nothing more"
            )
            assert "https://" not in text
        finally:
            await db.close()

    run_db_test(run())


def test_json_export_preserves_provenance(tmp_path, monkeypatch):
    from blocklist.serialize import to_json

    async def run():
        db_path = str(tmp_path / "b2json.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            await _seed_catalog_row(
                db,
                domain="steamcommunity.com",
                raw_ioc="https://steamcommunity.com/profiles/123",
                host_ioc="steamcommunity.com",
            )

            payload = await build_mod.build_blocklist(db)
            doc = to_json(payload)
            rec = doc["domains"][0]
            # Enough provenance for an operator to reason about inclusion.
            for field in (
                "domain", "reason", "classification", "classification_enabled",
                "sources", "confidence", "confidence_level", "malware",
                "threat_type", "first_seen", "evidence",
            ):
                assert field in rec, f"missing field {field} in JSON record"
            evidence = rec["evidence"][0]
            for field in ("source", "ref_id", "ioc_type", "ioc_value", "raw_ioc", "host_ioc"):
                assert field in evidence, f"missing evidence field {field}"
        finally:
            await db.close()

    run_db_test(run())


def test_evidence_ordering_is_deterministic(tmp_path, monkeypatch):
    """Equivalent input rows in a different physical order must produce an
    identical payload (evidence lists, freshness factor, confidence)."""
    from blocklist.serialize import to_json

    async def run():
        dbs = []
        for variant, order in (
            ("a", ["a", "b", "c"]),
            ("b", ["c", "a", "b"]),
            ("c", ["b", "c", "a"]),
        ):
            db_path = str(tmp_path / f"det-{variant}.db")
            monkeypatch.setenv("DB_PATH", db_path)
            monkeypatch.setattr(database, "DB_PATH", db_path)
            await init_db()
            db = await database.get_db()
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            # The three variants share one backend connection when running
            # against live PostgreSQL (DB_PATH only isolates SQLite files), so
            # clear this test's rows before each variant to avoid unique-key
            # collisions on re-insert -- the comparison is about physical insert
            # order, not persistent table state.
            await db.execute(
                "DELETE FROM ti_mirror_iocs "
                "WHERE source = 'threatfox' AND ref_id IN ("
                "'tf-det-a.example', 'tf-det-b.example', 'tf-det-c.example')"
            )
            await db.commit()

            # Three catalog rows with different observed first_seen values,
            # inserted in different physical orders per variant.
            stamps = {"a": "2024-06-01", "b": "2024-06-02", "c": "2024-06-03"}
            for key in order:
                await _seed_catalog_row(
                    db,
                    domain=f"det-{key}.example",
                    first_seen=stamps[key],
                )

            payload = await build_mod.build_blocklist(db)
            dbs.append((to_json(payload), payload))
            await db.close()

        ref_json, ref_payload = dbs[0]
        for json_doc, payload in dbs[1:]:
            assert json_doc == ref_json, (
                "evidence ordering must be identical across row orderings"
            )
            for rec in ref_payload["domains"]:
                other = next(
                    r for r in payload["domains"] if r["domain"] == rec["domain"]
                )
                assert rec["evidence"] == other["evidence"]
                assert rec["confidence_factors"] == other["confidence_factors"]
                assert rec["confidence"] == other["confidence"]

    run_db_test(run())


def test_otx_earliest_observation_drives_freshness(tmp_path, monkeypatch):
    """When several OTX rows share a domain, the *earliest* observed_at must
    drive the freshness score (a fresh row never masks a stale one)."""
    async def run():
        db_path = str(tmp_path / "b1-min.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

            await replace_otx_cve_pulses(db, "CVE-2024-6003", _OTX_PULSE)
            # Insert fresh first, stale second — the earliest must win.
            await replace_otx_pulse_iocs(db, "pulse-fix", [
                {"ioc_type": "DOMAIN", "ioc_value": "min-stale.example",
                 "description": "C2", "observed_at": "2021-01-01T00:00:00Z"},
                {"ioc_type": "DOMAIN", "ioc_value": "min-stale.example",
                 "description": "C2", "observed_at": "2026-01-01T00:00:00Z"},
            ])
            await _seed_catalog_row(db, domain="min-stale.example", first_seen="2021-01-02")

            payload = await build_mod.build_blocklist(db)
            rec = next(
                r for r in payload["domains"] if r["domain"] == "min-stale.example"
            )
            freshness = next(
                (f for f in rec.get("confidence_factors") or [] if f["factor"] == "freshness"),
                None,
            )
            assert freshness is not None
            assert freshness.get("freshness_fallback") is not True
            assert freshness["value"] < 0.6, (
                "stale 2021 observation must dominate; fresh 2026 row must not mask it"
            )
        finally:
            await db.close()

    run_db_test(run())


# NOTE: pytest must be importable for the fixture marker above; imported lazily
# to keep the module importable without pytest (mirrors repo test conventions).
