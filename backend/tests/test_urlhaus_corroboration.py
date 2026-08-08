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
            assert set(otx_only["sources"]) == {"otx"}
        finally:
            await db.close()

    run_db_test(run())


def test_malwarebazaar_hash_corroboration_with_threatfox(tmp_path, monkeypatch):
    """A HASH edge corroborated by ThreatFox and MalwareBazaar rows reaches
    three distinct sources (otx + tf + mb) and saturates corroboration at 1.0
    — Phase 3 MalwareBazaar registration on the same evidence path."""
    sha = "e167b20f1acf48f7ce0ae33a218e2c1b300b41c012ededf03e7a3522a4ebe95e"

    async def run():
        db_path = str(tmp_path / "mb-corr.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published)
                VALUES
                    ('CVE-2024-7001', 'Alpha', '2024-01-01'),
                    ('CVE-2024-7002', 'Beta', '2024-01-02'),
                    ('CVE-2024-7003', 'Gamma', '2024-01-03')
                """
            )
            pulse = [
                {
                    "pulse_id": "pulse-hash-shared",
                    "pulse_name": "Shared hash",
                    "author": "analyst",
                    "created_date": "2024-01-05",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 1,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-7001", pulse)
            await replace_otx_cve_pulses(db, "CVE-2024-7002", pulse)
            await replace_otx_pulse_iocs(
                db,
                "pulse-hash-shared",
                [{"ioc_type": "HASH", "ioc_value": sha, "description": ""}],
            )

            for source, family in (("threatfox", "Quakbot"), ("malwarebazaar", "Emotet")):
                await db.execute(
                    """
                    INSERT INTO ti_mirror_iocs (
                        source, ref_id, ioc_type, ioc_value, raw_ioc, malware,
                        threat_type, confidence_level, first_seen
                    ) VALUES (
                        ?, ?, 'hash', ?, ?, ?, 'exe', 100, '2024-06-01'
                    )
                    """,
                    (source, f"{source}-hash", sha, sha, family),
                )
            await db.commit()

            peers = await find_shared_infrastructure_v2(db, "CVE-2024-7001", limit=10)
            by_peer = {p["cve_id_b"]: p for p in peers}
            corr = by_peer["CVE-2024-7002"]
            assert {"otx", "threatfox", "malwarebazaar"} <= set(corr["sources"])
            by_k = next(
                f for f in corr["confidence_factors"] if f["factor"] == "corroboration"
            )
            assert by_k["k_sources"] == 2
            assert by_k["k_receipts"] == 2
            assert by_k["value"] == 1.0
        finally:
            await db.close()

    run_db_test(run())


def test_retro_match_hits_urlhaus_and_malwarebazaar_mirrors(tmp_path, monkeypatch):
    """Phase 3 retro-match cutover: watchlist entries join the unified
    ti_mirror_iocs store across ALL catalog sources, not just ThreatFox."""
    from ioc.retro_match import find_retro_matches

    sha = "e167b20f1acf48f7ce0ae33a218e2c1b300b41c012efecef03e7a3522a4ebe95e"

    async def run():
        db_path = str(tmp_path / "retro3.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO users (id, username, password_hash, role, is_active) "
                "VALUES (1, 'pytest-admin', 'hash', 'admin', 1)"
            )
            await db.execute(
                "INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value) VALUES (1, 'hash', ?)",
                (sha,),
            )
            await db.execute(
                "INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value) VALUES (1, 'domain', 'evil.example')"
            )
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
                    threat_type, confidence_level, first_seen
                ) VALUES ('urlhaus', 'uh1', 'url', 'http://evil.example/a.exe',
                           'http://evil.example/a.exe', 'evil.example', 'emotet',
                           'malware_download', 100, '2024-07-01')
                """
            )
            await db.execute(
                """
                INSERT INTO ti_mirror_iocs (
                    source, ref_id, ioc_type, ioc_value, raw_ioc, malware,
                    threat_type, confidence_level, first_seen
                ) VALUES ('malwarebazaar', ?, 'hash', ?, ?, 'Emotet',
                           'exe', 97, '2024-07-02')
                """,
                (sha, sha, sha),
            )
            await db.commit()

            matches = await find_retro_matches(db)
            sources = {m["source"] for m in matches}
            assert {"urlhaus", "malwarebazaar"} <= sources
            uh = next(m for m in matches if m["source"] == "urlhaus")
            assert uh["mirror_malware"] == "emotet"
            mb = next(m for m in matches if m["source"] == "malwarebazaar")
            assert mb["mirror_confidence"] == 97
        finally:
            await db.close()

    run_db_test(run())
