"""Correlation v2 Phase 1 — pulse campaigns, IOC normalization, hub suppression."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation.campaigns import (
    build_campaigns_from_pulses,
    campaign_id_for_pulse,
    get_campaigns_for_cve,
    prune_invalid_campaign_members,
)
from correlation.engine import get_correlation_for_cve
from correlation.hub_suppress import filter_campaign_members, is_hub_cve
from correlation.ioc_normalize import is_noise_ip, normalize_ioc, refang
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database


async def _seed_db(db_path: str, *, include_hub: bool = False):
    database.DB_PATH = db_path
    await init_db()
    db = await database.get_db()
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
        VALUES
            ('CVE-2024-1001', 'Alpha', '2024-01-01', 0, 0, 0.1),
            ('CVE-2024-1002', 'Beta', '2024-01-02', 0, 0, 0.2),
            ('CVE-2024-1003', 'Gamma', '2024-01-03', 0, 0, 0.3),
            ('CVE-2024-HUB1', 'Hub', '2024-01-04', 1, 1, 0.9)
        """
    )
    pulses_a = [
        {
            "pulse_id": "pulse-campaign-1",
            "pulse_name": "Ransomware wave Q1",
            "author": "analyst1",
            "created_date": "2024-01-10",
            "adversary": "APT-TEST",
            "malware_families": ["locker-x"],
            "tags": ["ransomware"],
            "targeted_countries": ["US", "GB"],
            "ioc_count": 2,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses_a)
    await replace_otx_cve_pulses(db, "CVE-2024-1002", pulses_a)

    pulses_b = [
        {
            "pulse_id": "pulse-solo",
            "pulse_name": "Solo pulse",
            "author": "analyst2",
            "created_date": "2024-02-01",
            "adversary": "",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 0,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-1003", pulses_b)

    if include_hub:
        hub_pulses = [
            {
                "pulse_id": f"pulse-hub-{i}",
                "pulse_name": f"Hub pulse {i}",
                "author": "crowd",
                "created_date": "2024-01-01",
                "adversary": "",
                "malware_families": [],
                "tags": [],
                "targeted_countries": [],
                "ioc_count": 1,
            }
            for i in range(55)
        ]
        await replace_otx_cve_pulses(db, "CVE-2024-HUB1", hub_pulses)
        await replace_otx_cve_pulses(db, "CVE-2024-1003", pulses_b + hub_pulses[:1])

    await replace_otx_pulse_iocs(
        db,
        "pulse-campaign-1",
        [
            {"ioc_type": "IPv4", "ioc_value": "192.168.1.10", "description": ""},
            {"ioc_type": "domain", "ioc_value": "evil[.]example.com", "description": ""},
        ],
    )
    await db.commit()
    return db


def test_refang_and_normalize_ioc_types():
    assert refang("hxxp://evil[.]example[.]com") == "http://evil.example.com"
    typ, val, meta = normalize_ioc("IPv4", "192.168.1.5")  # type: ignore[misc]
    assert typ == "IP"
    assert val == "192.168.1.5"
    assert meta["is_noise_ip"] is True
    assert is_noise_ip("10.0.0.1") is True
    domain = normalize_ioc("domain", "EVIL.EXAMPLE.COM")
    assert domain is not None
    assert domain[1] == "evil.example.com"


def test_pulse_cooccurrence_builds_campaign(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            stats = await build_campaigns_from_pulses(db)
            await db.commit()
            assert stats["campaigns"] == 1
            assert stats["members"] == 2

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert len(campaigns) == 1
            assert campaigns[0]["campaign_id"] == campaign_id_for_pulse("pulse-campaign-1")
            assert set(campaigns[0]["members"]) == {"CVE-2024-1001", "CVE-2024-1002"}
            assert campaigns[0]["evidence"][0]["type"] == "same_pulse"
        finally:
            await db.close()

    asyncio.run(run())


def test_hub_cve_suppression_limits_members(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-hub.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("CORRELATION_HUB_CVE_PULSE_CAP", "50")
        db = await _seed_db(db_path, include_hub=True)
        try:
            pulse_counts = {"CVE-2024-HUB1": 55, "CVE-2024-1001": 2}
            peers = ["CVE-2024-HUB1"] + [f"CVE-2024-{i:04d}" for i in range(30)]
            filtered = filter_campaign_members("CVE-2024-1001", peers, pulse_counts)
            assert "CVE-2024-HUB1" not in filtered
            assert is_hub_cve(55) is True
        finally:
            await db.close()

    asyncio.run(run())


def test_ioc_normalization_at_ingest(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-ioc.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            rows = await db.execute_fetchall(
                """
                SELECT ioc_type, ioc_value FROM otx_pulse_iocs
                WHERE pulse_id = 'pulse-campaign-1'
                ORDER BY ioc_value
                """
            )
            types = {row["ioc_type"] for row in rows}
            values = {row["ioc_value"] for row in rows}
            assert "IP" in types
            assert "192.168.1.10" in values
            assert "evil.example.com" in values
        finally:
            await db.close()

    asyncio.run(run())


def test_get_correlation_includes_campaigns_and_v2_cache(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-api.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("OTX_API_KEY", "test-key")
        db = await _seed_db(db_path)
        try:
            await build_campaigns_from_pulses(db)
            await db.commit()

            result = await get_correlation_for_cve(db, "CVE-2024-1001")
            assert result["meta"]["engine_version"] == "2.0"
            assert result["otx_status"] == "ok"
            assert len(result["campaigns"]) == 1

            cached = await get_correlation_for_cve(db, "CVE-2024-1001")
            assert cached["campaigns"][0]["campaign_id"] == result["campaigns"][0]["campaign_id"]
        finally:
            await db.close()

    asyncio.run(run())


def test_prune_invalid_campaign_members(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-prune.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            await build_campaigns_from_pulses(db)
            await db.execute("DELETE FROM cves WHERE cve_id = 'CVE-2024-1002'")
            removed = await prune_invalid_campaign_members(db)
            assert removed == 1
            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert campaigns == []
        finally:
            await db.close()

    asyncio.run(run())


def test_targeted_countries_stored_on_pulse_dimension(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-countries.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            row = await db.execute_fetchall(
                "SELECT targeted_countries FROM otx_pulses WHERE pulse_id = 'pulse-campaign-1'"
            )
            countries = json.loads(row[0]["targeted_countries"])
            assert countries == ["US", "GB"]
        finally:
            await db.close()

    asyncio.run(run())


def test_multi_ioc_infrastructure_has_evidence(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-infra.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            from correlation.ioc_graph import find_shared_infrastructure_v2

            rows = await find_shared_infrastructure_v2(db, "CVE-2024-1001")
            assert rows
            row = rows[0]
            assert row["shared_hash_count"] + row["shared_domain_count"] >= 1
            assert row["evidence"]
            assert row["summary"]
        finally:
            await db.close()

    asyncio.run(run())


def test_suppression_hides_campaign(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-suppress.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            from correlation.suppressions import add_suppression

            await build_campaigns_from_pulses(db)
            await db.commit()
            camp_id = campaign_id_for_pulse("pulse-campaign-1")
            await add_suppression(
                db,
                "CVE-2024-1001",
                "campaign_id",
                {"campaign_id": camp_id},
            )
            await db.commit()
            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert campaigns == []
        finally:
            await db.close()

    asyncio.run(run())


def test_greynoise_benign_downgrades_ip_edge():
    from correlation.confidence import confidence_for_ioc_edge

    level, why = confidence_for_ioc_edge(
        "IP",
        confirmations={"greynoise": "benign"},
    )
    assert level == "low"
    assert why


def test_related_cves_for_ioc_from_tables(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-ioc-related.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            from correlation.ioc_graph import related_cves_for_ioc

            related = await related_cves_for_ioc(db, "domain", "evil.example.com")
            assert "CVE-2024-1001" in related
            assert "CVE-2024-1002" in related
        finally:
            await db.close()

    asyncio.run(run())


def test_confirmations_batch_matches_per_value_cache(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-confirm-batch.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            from correlation.confirm import confirmations_for_iocs_batch
            from database import set_ioc_cache

            await set_ioc_cache(
                db, "1.2.3.4", "IP", {"greynoise": {"classification": "malicious"}}
            )
            await set_ioc_cache(
                db, "5.6.7.8", "IP", {"greynoise": {"classification": "benign"}}
            )
            await db.commit()

            out = await confirmations_for_iocs_batch(db, ["1.2.3.4", "5.6.7.8", "9.9.9.9"])
            assert out["1.2.3.4"]["greynoise"] == "malicious"
            assert out["5.6.7.8"]["greynoise"] == "benign"
            assert "9.9.9.9" not in out
        finally:
            await db.close()

    asyncio.run(run())


def test_shared_hash_pulls_uncopulsed_cve_into_campaign(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-hash-expand.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            shared_hash = "a" * 32
            await replace_otx_pulse_iocs(
                db,
                "pulse-campaign-1",
                [
                    {"ioc_type": "IPv4", "ioc_value": "192.168.1.10", "description": ""},
                    {"ioc_type": "domain", "ioc_value": "evil[.]example.com", "description": ""},
                    {"ioc_type": "hash", "ioc_value": shared_hash, "description": ""},
                ],
            )
            await replace_otx_pulse_iocs(
                db, "pulse-solo", [{"ioc_type": "hash", "ioc_value": shared_hash, "description": ""}]
            )
            await build_campaigns_from_pulses(db)
            await db.commit()

            # CVE-2024-1003 was only ever tagged in pulse-solo, never co-pulsed
            # with CVE-2024-1001 — but they now share a hash IOC.
            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert len(campaigns) == 1
            assert "CVE-2024-1003" in campaigns[0]["members"]
        finally:
            await db.close()

    asyncio.run(run())


def test_compute_correlation_priority_breakdown():
    from correlation.priority import compute_correlation_priority

    result = {
        "campaigns": [{"confidence": "high", "label": "Ransomware wave"}],
        "infrastructure": [{"confidence": "medium", "cve_id_b": "CVE-2024-9999", "shared_ioc_count": 2}],
        "actor": [{"confidence": "medium", "actor_name": "APT-TEST", "user_sector_match": True}],
        "temporal": [{
            "vendor": "wordpress",
            "anomaly_score": 4.0,
            "current_week_count": 15,
            "average_weekly_count": 1.6,
        }],
    }
    priority = compute_correlation_priority(result)
    assert priority["score"] > 0
    temporal = next(c for c in priority["components"] if c["signal"] == "temporal")
    assert "Wordpress" in temporal["sentence"]
    assert "15 published" in temporal["sentence"]
    assert priority["components"][0]["signal"] == "campaign"
    signals = {c["signal"] for c in priority["components"]}
    assert signals == {"campaign", "infrastructure", "actor", "temporal"}

    empty = compute_correlation_priority({})
    assert empty == {"score": 0, "components": []}


def test_get_correlation_error_path_hides_exception_text(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "corr-error-path.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            import correlation.campaigns as campaigns_mod

            async def _boom(*args, **kwargs):
                raise RuntimeError("super secret internal detail")

            monkeypatch.setattr(campaigns_mod, "get_campaigns_for_cve", _boom)

            result = await get_correlation_for_cve(db, "CVE-2024-1001")
            assert result["otx_status"] == "degraded"
            assert result["error"] == "correlation_unavailable"
            assert "super secret" not in str(result)
            assert result["priority"] == {"score": 0, "components": []}
        finally:
            await db.close()

    asyncio.run(run())
