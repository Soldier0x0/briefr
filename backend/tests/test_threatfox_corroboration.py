"""CORR-PR-10: ThreatFox corroboration on IOC edges."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from correlation.ioc_graph import find_shared_infrastructure_v2
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database


async def _seed_shared_infrastructure(db) -> None:
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published)
        VALUES
            ('CVE-2024-5001', 'Alpha', '2024-01-01'),
            ('CVE-2024-5002', 'Beta', '2024-01-02'),
            ('CVE-2024-5003', 'Gamma', '2024-01-03')
        """
    )
    pulse_a = [
        {
            "pulse_id": "pulse-corr",
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
            "pulse_id": "pulse-otx",
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
    await replace_otx_cve_pulses(db, "CVE-2024-5001", pulse_a + pulse_b)
    await replace_otx_cve_pulses(db, "CVE-2024-5002", pulse_a)
    await replace_otx_cve_pulses(db, "CVE-2024-5003", pulse_b)

    await replace_otx_pulse_iocs(
        db,
        "pulse-corr",
        [{"ioc_type": "DOMAIN", "ioc_value": "corroborated.example", "description": ""}],
    )
    await replace_otx_pulse_iocs(
        db,
        "pulse-otx",
        [{"ioc_type": "DOMAIN", "ioc_value": "otx-only.example", "description": ""}],
    )


def test_threatfox_corroboration_outranks_otx_only(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "tf-corr.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_shared_infrastructure(db)
            await db.execute(
                """
                INSERT INTO threatfox_iocs (
                    ioc_id, ioc_type, ioc_value, raw_ioc, malware, threat_type,
                    confidence_level, first_seen
                ) VALUES (
                    'tf-corr-1', 'domain', 'corroborated.example', 'corroborated.example',
                    'vidar', 'botnet_cc', 90, '2024-06-01'
                )
                """
            )
            await db.commit()

            peers = await find_shared_infrastructure_v2(db, "CVE-2024-5001", limit=10)
            assert len(peers) == 2

            by_peer = {p["cve_id_b"]: p for p in peers}
            corroborated = by_peer["CVE-2024-5002"]
            otx_only = by_peer["CVE-2024-5003"]

            rank = {"low": 0, "medium": 1, "high": 2}
            assert rank[corroborated["confidence"]] >= rank[otx_only["confidence"]]
            corr_factor = next(
                f["value"] for f in corroborated["confidence_factors"] if f["factor"] == "corroboration"
            )
            otx_factor = next(
                f["value"] for f in otx_only["confidence_factors"] if f["factor"] == "corroboration"
            )
            assert corr_factor > otx_factor
            assert "threatfox" in corroborated["sources"]
            assert corroborated["evidence"][0]["corroborated_by"] == ["threatfox:tf-corr-1"]
            assert "corroborated_by" not in otx_only["evidence"][0]
        finally:
            await db.close()

    run_db_test(run())


def test_batch_threatfox_hits_matches_canonical_domain(tmp_path, monkeypatch):
    from correlation.threatfox_corroboration import batch_threatfox_hits

    async def run():
        db_path = str(tmp_path / "tf-batch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO threatfox_iocs (
                    ioc_id, ioc_type, ioc_value, raw_ioc, malware, threat_type,
                    confidence_level, first_seen
                ) VALUES (
                    'tf-99', 'domain', 'evil.example', 'evil.example',
                    'emotet', 'payload_delivery', 75, '2024-05-01'
                )
                """
            )
            await db.commit()
            hits = await batch_threatfox_hits(db, [("DOMAIN", "EVIL.EXAMPLE")])
            key = ("DOMAIN", "evil.example")
            assert key in hits
            assert hits[key][0]["ioc_id"] == "tf-99"
        finally:
            await db.close()

    run_db_test(run())
