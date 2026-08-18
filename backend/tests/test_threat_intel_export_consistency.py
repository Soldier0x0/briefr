"""Consistency and regression tests for the threat-intel export formats.

All three exports (TXT, CSV, JSON) must derive from the *same* canonical build
result (`blocklist.build.build_blocklist`) so they cannot diverge. This file
pins:

- The canonical candidate record now carries `ioc_type` + `exact_ioc`.
- CSV exports the exact upstream IOC (never a derived domain), with columns
  type, value, source, confidence, first_seen, malware, threat_type.
- TXT/CSV/JSON produced from one build agree on the same candidate set and
  metadata.
- URL IOCs (URLhaus `ioc_type='url'` and ThreatFox URL-downcast rows whose
  `raw_ioc` is a URL) preserve the exact URL in the CSV `value` cell.

The ip/hash test is a *regression/documentation* test for the current builder:
`db.blocklist.fetch_catalog_evidence` intentionally selects only ioc_type
'domain'/'url', so IP and hash mirror rows are outside blocklist scope today.
This does NOT assert they must remain excluded forever — it only documents
that the current pipeline never emits them.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from settings import settings

import blocklist.build as build_mod
import database
import db.blocklist as db_blocklist
from blocklist.serialize import to_csv, to_json, to_txt
from database import get_db, init_db
from tests.conftest import run_db_test

_CSV_HEADERS = ["type", "value", "source", "confidence", "first_seen", "malware", "threat_type"]


@pytest.fixture
def client_scoped(tmp_path, monkeypatch):
    """TestClient bound to an isolated SQLite DB (Postgres-only classification
    table stubbed away by the calling test)."""
    db_path = tmp_path / "export_consistency.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


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
    ioc_type: str = "domain",
    malware: str = "redline",
    threat_type: str = "botnet_cc",
    confidence_level: int = 90,
) -> None:
    ref = f"{source}-{domain}-{ioc_type}"
    await db.execute(
        """
        INSERT INTO ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
            threat_type, confidence_level, first_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            ref,
            ioc_type,
            domain if ioc_type != "url" else (raw_ioc or domain),
            raw_ioc or domain,
            host_ioc,
            malware,
            threat_type,
            confidence_level,
            first_seen,
        ),
    )
    await db.commit()


def _patch_fetch_no_infra(monkeypatch):
    monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
    monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)


def _setup_db(tmp_path, monkeypatch, name):
    db_path = str(tmp_path / name)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)


def test_ioc_type_and_exact_ioc_for_domain_and_url(tmp_path, monkeypatch):
    """Domain evidence → ioc_type 'domain'; URL evidence / URL raw_ioc →
    ioc_type 'url' with the exact URL preserved as exact_ioc."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-a.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await _seed_catalog_row(db, domain="basic.example")
            await _seed_catalog_row(
                db,
                domain="drive.google.com",
                raw_ioc="https://drive.google.com/uc?export=download&id=ABC",
                host_ioc="drive.google.com",
                source="threatfox",
            )
            await _seed_catalog_row(
                db,
                domain="bad.example",
                raw_ioc="https://bad.example/loader?token=x",
                host_ioc="bad.example",
                source="urlhaus",
                ioc_type="url",
            )

            payload = await build_mod.build_blocklist(db)
            by_domain = {r["domain"]: r for r in payload["domains"]}

            basic = by_domain["basic.example"]
            assert basic["ioc_type"] == "domain"
            assert basic["exact_ioc"] == "basic.example"

            gf = by_domain["drive.google.com"]
            assert gf["ioc_type"] == "url", (
                "ThreatFox URL-downcast rows keep the URL in raw_ioc; content "
                "must decide the type, not the stored ioc_type='domain'"
            )
            assert gf["exact_ioc"] == (
                "https://drive.google.com/uc?export=download&id=ABC"
            ), "exact_ioc must preserve the upstream URL verbatim"

            ul = by_domain["bad.example"]
            assert ul["ioc_type"] == "url"
            assert ul["exact_ioc"] == "https://bad.example/loader?token=x"
        finally:
            await db.close()

    run_db_test(run())


def test_csv_columns_and_domain_value(tmp_path, monkeypatch):
    """CSV headers are exactly the agreed columns; a domain row's value is the
    canonical domain and multi-valued cells are ;-joined."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-b.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await _seed_catalog_row(
                db,
                domain="basic.example",
                malware="redline",
                threat_type="botnet_cc",
            )
            payload = await build_mod.build_blocklist(db)
            table = list(csv.reader(io.StringIO(to_csv(payload))))
            assert table[0] == _CSV_HEADERS, table[0]
            assert len(table) == 2
            row = table[1]
            assert row[0] == "domain"
            assert row[1] == "basic.example"
            assert row[4] == "2024-06-01"
            assert "redline" in row[5]
            assert "botnet_cc" in row[6]
        finally:
            await db.close()

    run_db_test(run())


def test_csv_url_preserves_exact_url_not_domain(tmp_path, monkeypatch):
    """A URL-backed candidate's CSV value is the full URL — never a derived
    domain. This is the no-substitution guarantee."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-c.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            url = "https://steamcommunity.com/profiles/123?x=1%2F2"
            await _seed_catalog_row(
                db,
                domain="steamcommunity.com",
                raw_ioc=url,
                host_ioc="steamcommunity.com",
            )
            payload = await build_mod.build_blocklist(db)
            table = list(csv.reader(io.StringIO(to_csv(payload))))
            assert len(table) == 2
            row = table[1]
            assert row[0] == "url"
            assert row[1] == url, (
                "CSV value must be the exact URL, not the derived domain"
            )
            assert row[1] != "steamcommunity.com"
        finally:
            await db.close()

    run_db_test(run())


def test_csv_excludes_ineligible(tmp_path, monkeypatch):
    """Only eligible candidates appear in the CSV body (matches TXT semantics)."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-d.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await _seed_catalog_row(db, domain="ok.example")
            # OTX-only candidate without catalog corroboration → excluded.
            from database import replace_otx_cve_pulses, replace_otx_pulse_iocs
            await replace_otx_cve_pulses(db, "CVE-2026-0001", [{
                "pulse_id": "pulse-excl",
                "pulse_name": "Excl pulse",
                "author": "analyst",
                "created_date": "2025-01-01",
                "adversary": "",
                "malware_families": [],
                "tags": [],
                "targeted_countries": [],
                "ioc_count": 1,
            }])
            await replace_otx_pulse_iocs(db, "pulse-excl", [{
                "ioc_type": "DOMAIN",
                "ioc_value": "otx-only.example",
                "description": "C2",
            }])
            payload = await build_mod.build_blocklist(db)
            assert any(
                d["domain"] == "otx-only.example" and not d["eligible"]
                for d in payload["excluded"]
            )
            table = list(csv.reader(io.StringIO(to_csv(payload))))
            values = [row[1] for row in table[1:]]
            assert "ok.example" in values
            assert "otx-only.example" not in values
        finally:
            await db.close()

    run_db_test(run())


def test_formats_share_same_build_and_generated_at(tmp_path, monkeypatch):
    """One build feeds all three serializers with identical metadata."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-e.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await _seed_catalog_row(db, domain="aa.example")
            await _seed_catalog_row(db, domain="bb.example")

            payload = await build_mod.build_blocklist(db)
            generated_at = payload["meta"]["generated_at"]

            txt = to_txt(payload)
            assert f"# generated_at: {generated_at}" in txt
            assert "# mode: domains" in txt
            assert "# eligible: 2" in txt

            json_doc = to_json(payload)
            assert json_doc["meta"]["generated_at"] == generated_at
            assert json_doc["meta"]["eligible_count"] == 2

            table = list(csv.reader(io.StringIO(to_csv(payload))))
            assert len(table) == 3, "header + 2 eligible rows"
        finally:
            await db.close()

    run_db_test(run())


def test_txt_csv_json_same_candidates(tmp_path, monkeypatch):
    """TXT/CSV/JSON from one build agree on the candidate set and row counts.
    Cross-format divergence is impossible because they share one payload.
    Note: CSV value cells carry the *exact* IOC (a URL stays the URL), so the
    candidate set is compared via the row count and the domain-side evidence,
    not by asserting value == domain for URL-backed candidates."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-f.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            await _seed_catalog_row(db, domain="dom.example")
            await _seed_catalog_row(
                db,
                domain="url.example",
                raw_ioc="https://url.example/payload.bin",
                host_ioc="url.example",
                source="urlhaus",
                ioc_type="url",
            )

            payload = await build_mod.build_blocklist(db)
            eligible = {r["domain"] for r in payload["domains"] if r["eligible"]}
            assert eligible == {"dom.example", "url.example"}

            txt_domains = set(
                line for line in to_txt(payload, mode="domains").splitlines()
                if line and not line.startswith("#")
            )
            json_domains = {
                r["domain"] for r in to_json(payload)["domains"] if r["eligible"]
            }
            csv_rows = list(csv.reader(io.StringIO(to_csv(payload))))[1:]

            assert txt_domains == json_domains, "TXT and JSON must agree on candidates"
            assert len(csv_rows) == len(eligible), (
                "CSV must have exactly one row per eligible candidate"
            )
            csv_by_type = {row[0] for row in csv_rows}
            assert csv_by_type == {"domain", "url"}
            # Domain-backed candidate keeps its canonical domain as the value.
            domain_row = next(r for r in csv_rows if r[0] == "domain")
            assert domain_row[1] == "dom.example"
            # URL-backed candidate preserves the exact URL, not a derived domain.
            url_row = next(r for r in csv_rows if r[0] == "url")
            assert url_row[1] == "https://url.example/payload.bin"
            assert url_row[1] != "url.example"
        finally:
            await db.close()

    run_db_test(run())


def test_ip_hash_rows_outside_blocklist_scope_today(tmp_path, monkeypatch):
    """Regression/documentation: the current blocklist builder only selects
    ioc_type 'domain'/'url', so IP and hash mirror rows never appear in any
    export. This documents current behavior — it is NOT a promise that these
    types must remain excluded forever."""
    async def run():
        _setup_db(tmp_path, monkeypatch, "cs-g.db")
        await init_db()
        db = await get_db()
        try:
            _patch_fetch_no_infra(monkeypatch)
            for src, ref, ctype, value in [
                ("threatfox", "ip-1", "ip", "1.20.91.236"),
                ("threatfox", "hash-1", "hash", "a" * 64),
                ("urlhaus", "ip-2", "ip", "1.62.79.200"),
            ]:
                await db.execute(
                    """
                    INSERT INTO ti_mirror_iocs (
                        source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc,
                        malware, threat_type, confidence_level, first_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (src, ref, ctype, value, value, "", "xworm", "c2", 85, "2024-08-01"),
                )
            await db.commit()

            payload = await build_mod.build_blocklist(db)
            assert payload["meta"]["candidate_count"] == 0, (
                "IP/hash rows are filtered out by the catalog SQL today"
            )

            assert to_txt(payload).splitlines() == [
                "# BRIEFR malicious-domain candidates",
                f"# generated_at: {payload['meta']['generated_at']}",
                "# mode: domains",
                "# eligible: 0",
                "# excluded: 0",
            ]
            table = list(csv.reader(io.StringIO(to_csv(payload))))
            assert table == [_CSV_HEADERS], "no IP/hash rows in CSV"
            assert to_json(payload)["domains"] == []
        finally:
            await db.close()

    run_db_test(run())


def test_public_and_admin_csv_endpoints(client_scoped, tmp_path, monkeypatch):
    """The CSV endpoint renders on both the public token-gated route and the
    admin route (smoke coverage; full auth semantics live in the existing
    public-endpoint and admin-router test files)."""
    monkeypatch.setattr(settings, "threat_intel_token", "test-export-token")
    _patch_fetch_no_infra(monkeypatch)

    from tests.conftest import seed_pytest_auth_user_if_missing
    seed_pytest_auth_user_if_missing()

    headers = {"X-BRIEFR-Intel-Token": "test-export-token"}

    public = client_scoped.get("/api/threat-intel/blocklist.csv", headers=headers)
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("text/csv")

    admin = client_scoped.get("/api/admin/threat-intel/blocklist.csv")
    assert admin.status_code == 200
    assert admin.headers["content-type"].startswith("text/csv")