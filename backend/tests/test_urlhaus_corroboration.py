"""Phase 2: URLhaus corroboration on DOMAIN and URL edges."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from correlation.ioc_graph import find_shared_infrastructure_v2
from correlation.source_evidence import batch_source_evidence
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database


async def _seed_shared_infrastructure(db) -> None:
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published)
        VALUES
            ('CVE-2024-6001', 'Alpha', '2024-01-01'),
            ('CVE-2024-6002', 'Beta', '2024-01-02'),
            ('CVE-2024-6003', 'Gamma', '2024-01-03')
        """
    )
    pulse_a = [
        {
            "pulse_id": "pulse-corr-urlhaus",
            "pulse_name": "Corroborated link",
            "author": "analyst",
            "created_date": "2024-01-05",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    pulse_b = [
        {
            "pulse_id": "pulse-otx-urlhaus",
            "pulse_name": "OTX-only link",
            "author": "analyst",
            "created_date": "2024-01-06",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-6001", pulse_a + pulse_b)
    await replace_otx_cve_pulses(db, "CVE-2024-6002", pulse_a)
    await replace_otx_cve_pulses(db, "CVE-2024-6003", pulse_b)

    await replace_otx_pulse_iocs(
        db,
        "pulse-corr-urlhaus",
        [{"ioc_type": "DOMAIN", "ioc_value": "corroborated.example", "description": ""}],
    )
    await replace_otx_pulse_iocs(
        db,
        "pulse-otx-urlhaus",
        [{"ioc_type": "DOMAIN", "ioc_value": "otx-only.example", "description": ""}],
    )


async def _seed_urlhaus_row(db, ref_id: str, ioc_value: str, host: str) -> None:
    await db.execute(
        """
        INSERT INTO ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
            threat_type, confidence_level, first_seen
        ) VALUES (
            'urlhaus', ?, 'url', ?, ?, ?, 'emotet', 'malware_download', 100, '2024-06-01'
        )
        """,
        (ref_id, ioc_value, ioc_value, host),
    )


def test_batch_source_evidence_matches_urlhaus_domain_and_url(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "uh-batch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_urlhaus_row(
                db, "uh-1", "http://shared.example/payload.bin", "shared.example"
            )
            await db.commit()
            hits = await batch_source_evidence(
                db,
                [
                    ("DOMAIN", "shared.example"),
                    ("URL", "http://shared.example/payload.bin"),
                ],
            )
            domain_key = ("DOMAIN", "shared.example")
            url_key = ("URL", "http://shared.example/payload.bin")
            assert domain_key in hits
            assert url_key in hits
            for key in (domain_key, url_key):
                assert any(r["source"] == "urlhaus" for r in hits[key])
        finally:
            await db.close()

    run_db_test(run())


def test_domain_edge_on_www_host_matches_urlhaus_row(tmp_path, monkeypatch):
    """A DOMAIN edge whose canonical value drops a leading ``www.`` must join
    the URLhaus URL row via host_ioc — regression for the www-asymmetry bug."""
    async def run():
        db_path = str(tmp_path / "uh-www.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_urlhaus_row(
                db, "uh-www", "http://www.evil.example/payload.bin", "evil.example"
            )
            await db.commit()
            hits = await batch_source_evidence(db, [("DOMAIN", "www.evil.example")])
            key = ("DOMAIN", "evil.example")
            assert key in hits
            assert any(r["source"] == "urlhaus" and r["ref_id"] == "uh-www" for r in hits[key])
        finally:
            await db.close()

    run_db_test(run())
    async def run():
        db_path = str(tmp_path / "uh-batch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_urlhaus_row(
                db, "uh-1", "http://shared.example/payload.bin", "shared.example"
            )
            await db.commit()
            hits = await batch_source_evidence(
                db,
                [
                    ("DOMAIN", "shared.example"),
                    ("URL", "http://shared.example/payload.bin"),
                ],
            )
            domain_key = ("DOMAIN", "shared.example")
            url_key = ("URL", "http://shared.example/payload.bin")
            assert domain_key in hits
            assert url_key in hits
            for key in (domain_key, url_key):
                assert any(r["source"] == "urlhaus" for r in hits[key])
        finally:
            await db.close()

    run_db_test(run())


def test_urlhaus_and_threatfox_corroboration_saturate_confidence(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "uh-corr.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_shared_infrastructure(db)
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, malware,
                    threat_type, confidence_level, first_seen
                ) VALUES (
                    'threatfox', 'tf-corr-1', 'domain', 'corroborated.example',
                    'corroborated.example', 'vidar', 'botnet_cc', 90, '2024-06-01'
                )
                """
            )
            await _seed_urlhaus_row(
                db, "uh-corr-1", "http://corroborated.example/a.exe", "corroborated.example"
            )
            await db.commit()

            peers = await find_shared_infrastructure_v2(db, "CVE-2024-6001", limit=10)
            by_peer = {p["cve_id_b"]: p for p in peers}
            corroborated = by_peer["CVE-2024-6002"]
            otx_only = by_peer["CVE-2024-6003"]

            assert set(corroborated["sources"]) == {"otx", "threatfox", "urlhaus"}
            corr_factor = next(
                f["value"]
                for f in corroborated["confidence_factors"]
                if f["factor"] == "corroboration"
            )
            assert corr_factor == 1.0
            corr_k = next(
                f for f in corroborated["confidence_factors"] if f["factor"] == "corroboration"
            )
            assert corr_k["k_sources"] == 2
            assert corr_k["k_receipts"] == 2

            otx_factor = next(
                f["value"]
                for f in otx_only["confidence_factors"]
                if f["factor"] == "corroboration"
            )
            assert corr_factor > otx_factor
            assert set(otx_only["sources"]) == {"otx"}
        finally:
            await db.close()

    run_db_test(run())
