"""Correlation v2 Phase 1 — pulse campaigns, IOC normalization, hub suppression."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

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


def test_normalize_ioc_emits_raw_and_host_meta():
    """Phase A: normalize_ioc must surface the raw value and, for URL/DOMAIN,
    the normalized host so persistence can store them as raw_ioc/host_ioc. Raw
    inputs that differ from their canonical form (defanged URL, non-canonical
    IPv6, uppercase hash, surrounding whitespace) prove the verbatim value is
    preserved rather than the canonical one."""
    url = normalize_ioc("URL", "hxxp://drive.google.com/uc?id=abc123")
    assert url is not None
    typ, val, meta = url
    assert typ == "URL"
    assert val == "http://drive.google.com/uc?id=abc123"
    assert meta["raw_value"] == "hxxp://drive.google.com/uc?id=abc123"
    assert meta["host"] == "drive.google.com"

    tme = normalize_ioc("URL", "https://t.me/still_stellc")
    assert tme is not None
    assert tme[2]["host"] == "t.me"

    steam = normalize_ioc("URL", "https://steamcommunity.com/profiles/7656119")
    assert steam is not None
    assert steam[2]["host"] == "steamcommunity.com"

    domain = normalize_ioc("DOMAIN", "EVIL.EXAMPLE.COM")
    assert domain is not None
    assert domain[2]["host"] == "evil.example.com"
    assert domain[2]["raw_value"] == "EVIL.EXAMPLE.COM"

    ip = normalize_ioc("IP", "2001:0db8:0000:0000:0000:ff00:0042:8329")
    assert ip is not None
    assert ip[1] == "2001:db8::ff00:42:8329"
    assert ip[2]["raw_value"] == "2001:0db8:0000:0000:0000:ff00:0042:8329"
    assert "host" not in ip[2]

    h = normalize_ioc("HASH", "A" * 64)
    assert h is not None
    assert h[1] == "a" * 64
    assert h[2]["raw_value"] == "A" * 64
    assert "host" not in h[2]

    padded = normalize_ioc("URL", "  https://drive.google.com/uc?id=abc123  ")
    assert padded is not None
    assert padded[1] == "https://drive.google.com/uc?id=abc123"
    assert padded[2]["raw_value"] == "  https://drive.google.com/uc?id=abc123  "
    assert padded[2]["host"] == "drive.google.com"


def test_is_noise_ip_covers_ipv6_public_resolvers():
    """Gemini review on PR #487: IPv4-only resolver set silently let IPv6
    variants of the same well-known resolvers through as non-noise."""
    assert is_noise_ip("2001:4860:4860::8888") is True  # Google
    assert is_noise_ip("2606:4700:4700::1111") is True  # Cloudflare
    assert is_noise_ip("2620:fe::fe") is True  # Quad9
    assert is_noise_ip("2620:119:35::35") is True  # OpenDNS
    assert is_noise_ip("2001:4860:4860::1234") is False  # not a listed resolver


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

    run_db_test(run())


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

    run_db_test(run())


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
            assert any(v == "evil.example.com" for v in values)
        finally:
            await db.close()

    run_db_test(run())


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

    run_db_test(run())


def test_get_correlation_read_path_does_not_write_correlation_actor(tmp_path, monkeypatch):
    """PR-O2 (CACHE-001): the GET path computes actor findings live but never
    writes correlation_actor — persistence is scheduler-only."""
    async def run():
        db_path = str(tmp_path / "corr-readonly.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("OTX_API_KEY", "test-key")
        db = await _seed_db(db_path)
        try:
            before = await db.execute_fetchall(
                "SELECT COUNT(*) AS n FROM correlation_actor"
            )
            result = await get_correlation_for_cve(db, "CVE-2024-1001")
            assert result["meta"]["engine_version"] == "2.0"
            after = await db.execute_fetchall(
                "SELECT COUNT(*) AS n FROM correlation_actor"
            )
            assert after[0]["n"] == before[0]["n"]
        finally:
            await db.close()

    run_db_test(run())


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

    run_db_test(run())


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

    run_db_test(run())


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
            # CORR-PR-5: confidence_factors reaches the peer-aggregate API shape
            assert row["confidence_factors"]
            assert all("factor" in f and "reason" in f for f in row["confidence_factors"])
        finally:
            await db.close()

    run_db_test(run())


def test_campaign_confidence_factors_reach_api_shape(tmp_path, monkeypatch):
    """CORR-PR-5: confidence_factors surfaces on get_campaigns_for_cve output."""
    async def run():
        db_path = str(tmp_path / "corr-campaign-factors.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            await build_campaigns_from_pulses(db)
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert campaigns
            factors = campaigns[0]["confidence_factors"]
            assert factors
            assert all("factor" in f and "reason" in f for f in factors)
            assert factors[0]["factor"] == "same_pulse"
        finally:
            await db.close()

    run_db_test(run())


def test_peer_truncation_keeps_strongest_peer_over_alphabetical(tmp_path, monkeypatch):
    """CORR-PR-1 / D1: a 25-peer fixture where the strongest (hash-sharing)
    peer sorts alphabetically last must still survive a limit=20 truncation.
    """

    async def run():
        db_path = str(tmp_path / "corr-peer-rank.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        database.DB_PATH = db_path
        await init_db()
        db = await database.get_db()
        try:
            weak_ids = [f"CVE-2024-30{i:02d}" for i in range(1, 25)]  # 24 peers
            strong_id = "CVE-2024-9999"  # sorts alphabetically last

            await db.execute(
                "INSERT INTO cves (cve_id, description, published, is_kev, "
                "has_poc, epss_score) VALUES ('CVE-2024-3000', 'Base', "
                "'2024-01-01', 0, 0, 0.1)"
            )
            for peer in weak_ids + [strong_id]:
                await db.execute(
                    "INSERT INTO cves (cve_id, description, published, "
                    "is_kev, has_poc, epss_score) VALUES (?, 'Peer', "
                    "'2024-01-01', 0, 0, 0.1)",
                    (peer,),
                )

            base_iocs = [
                {"ioc_type": "IPv4", "ioc_value": f"203.0.113.{i}", "description": ""}
                for i in range(1, 25)
            ] + [
                {
                    "ioc_type": "SHA256",
                    "ioc_value": "a" * 64,
                    "description": "",
                }
            ]
            await replace_otx_cve_pulses(
                db,
                "CVE-2024-3000",
                [{
                    "pulse_id": "pulse-base",
                    "pulse_name": "Base pulse",
                    "author": "analyst1",
                    "created_date": "2024-01-01",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": len(base_iocs),
                }],
            )
            await replace_otx_pulse_iocs(db, "pulse-base", base_iocs)

            for i, peer in enumerate(weak_ids, start=1):
                pulse_id = f"pulse-weak-{i}"
                await replace_otx_cve_pulses(
                    db,
                    peer,
                    [{
                        "pulse_id": pulse_id,
                        "pulse_name": f"Weak pulse {i}",
                        "author": "analyst1",
                        "created_date": "2024-01-01",
                        "adversary": "",
                        "malware_families": [],
                        "tags": [],
                        "targeted_countries": [],
                        "ioc_count": 1,
                    }],
                )
                await replace_otx_pulse_iocs(
                    db,
                    pulse_id,
                    [{
                        "ioc_type": "IPv4",
                        "ioc_value": f"203.0.113.{i}",
                        "description": "",
                    }],
                )

            await replace_otx_cve_pulses(
                db,
                strong_id,
                [{
                    "pulse_id": "pulse-strong",
                    "pulse_name": "Strong pulse",
                    "author": "analyst1",
                    "created_date": "2024-01-01",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 1,
                }],
            )
            await replace_otx_pulse_iocs(
                db,
                "pulse-strong",
                [{
                    "ioc_type": "SHA256",
                    "ioc_value": "a" * 64,
                    "description": "",
                }],
            )
            await db.commit()

            from correlation.ioc_graph import find_shared_infrastructure_v2

            results = await find_shared_infrastructure_v2(
                db, "CVE-2024-3000", limit=20
            )
            assert len(results) == 20
            peer_ids = [r["cve_id_b"] for r in results]
            assert strong_id in peer_ids, (
                "hash-sharing peer must survive truncation over weaker "
                "alphabetically-earlier IP-sharing peers"
            )
            assert results[0]["cve_id_b"] == strong_id
            assert results[0]["confidence"] == "high"
        finally:
            await db.close()

    run_db_test(run())


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

    run_db_test(run())


def test_greynoise_benign_downgrades_ip_edge():
    from correlation.confidence import confidence_for_ioc_edge

    level, why, factors = confidence_for_ioc_edge(
        "IP",
        confirmations={"greynoise": "benign"},
    )
    assert level == "low"
    assert why
    assert any(f["factor"] == "confirmation" for f in factors)


def test_ioc_degree_never_raises_confidence():
    """CORR-PR-3 invariant: degree only ever lowers confidence."""
    from correlation.confidence import confidence_for_ioc_edge

    level_no_degree, _, _ = confidence_for_ioc_edge("HASH", degree=0)
    level_low_degree, _, _ = confidence_for_ioc_edge("HASH", degree=2)
    assert level_no_degree == "high"
    assert level_low_degree == "high"  # degree <= 3: no penalty


def test_ioc_degree_50_hash_edge_downranks_to_low_with_hub_reason():
    """Spec's own literal test case (generalized: a HASH, not just IP --
    IP already defaults to 'low' regardless of degree, so the IP case
    trivially passes without this code; the real value is penalizing a
    HASH/DOMAIN edge that would otherwise stay 'high'/'medium' untouched,
    exactly D2's concern: 'popular hashes create dense cliques of
    plausible-looking edges across unrelated CVEs.'"""
    from correlation.confidence import confidence_for_ioc_edge

    level, why, _ = confidence_for_ioc_edge("HASH", degree=50)
    assert level == "low"
    assert why and "hub" in why.lower()


def test_ioc_degree_50_ip_edge_stays_low_with_hub_reason():
    """The spec's literal test case, verified directly."""
    from correlation.confidence import confidence_for_ioc_edge

    level, why, _ = confidence_for_ioc_edge("IP", degree=50)
    assert level == "low"
    assert why and "hub" in why.lower()


def test_ioc_degree_moderate_downranks_by_one_level():
    from correlation.confidence import confidence_for_ioc_edge

    level, why, factors = confidence_for_ioc_edge("HASH", degree=7)
    # Rule-based downrank reaches medium; numeric §7 score (incl. corroboration k=1)
    # caps the edge at low for a degree-7 hub.
    assert level == "low"
    assert any(f["factor"] == "degree" for f in factors)


def test_ioc_degree_penalty_applies_after_confirmation_bump():
    """A confirmation-based bump must not rescue a hub edge back up --
    degree is applied last, per the 'only ever lowers' invariant."""
    from correlation.confidence import confidence_for_ioc_edge

    level, why, _ = confidence_for_ioc_edge(
        "DOMAIN",
        confirmations={"malwarebazaar": True},  # would bump medium->high alone
        degree=50,
    )
    assert level == "low"
    assert why and "hub" in why.lower()


def test_confidence_factors_snapshot_for_ioc_edge_and_campaign():
    """CORR-PR-5: confidence_factors is an additive, ordered trace of every
    step that moved the level -- not just the last why_not_higher string."""
    from correlation.confidence import campaign_confidence, confidence_for_ioc_edge

    level, why, factors = confidence_for_ioc_edge("HASH", degree=50)
    assert level == "low"
    factor_names = [f["factor"] for f in factors]
    assert factor_names == ["ioc_type", "degree", "corroboration", "freshness"]
    assert factors[1]["value"] == 50
    assert factors[1]["reason"] == why or factors[2]["reason"] == why

    level, why, factors = confidence_for_ioc_edge(
        "IP", confirmations={"greynoise": "malicious"}
    )
    assert level == "low"
    assert [f["factor"] for f in factors] == ["ioc_type", "confirmation", "corroboration", "freshness"]
    assert factors[1]["value"] == "greynoise_malicious"

    level, why, factors = campaign_confidence(
        "medium",
        [{"ioc_type": "HASH", "ioc_value": "abc"}],
        has_same_pulse=True,
    )
    assert level == "high"
    assert [f["factor"] for f in factors] == ["same_pulse", "shared_indicators"]

    level, why, factors = campaign_confidence("medium", [], has_same_pulse=True)
    assert level == "medium"
    assert [f["factor"] for f in factors] == ["same_pulse"]


def test_aggregate_infrastructure_why_matches_aggregate_confidence_edge():
    """Gemini review on PR #489: why_not_higher must come from an edge whose
    confidence equals the aggregate level, same filter as confidence_factors
    -- otherwise why can describe a weaker edge that lost the max() vote."""
    from correlation.confidence import aggregate_infrastructure_confidence

    edges = [
        {
            "ioc_type": "IP",
            "ioc_value": "1.2.3.4",
            "confidence": "low",
            "why_not_higher": "IP-only edges are weaker than domain or hash matches",
            "confidence_factors": [{"factor": "ip_only", "reason": "IP-only edges are weaker than domain or hash matches"}],
        },
        {
            "ioc_type": "HASH",
            "ioc_value": "a" * 64,
            "confidence": "high",
            "why_not_higher": None,
            "confidence_factors": [{"factor": "ioc_type", "value": "HASH", "reason": "Hash-type indicator"}],
        },
    ]
    confidence, evidence, why, factors = aggregate_infrastructure_confidence(edges)
    assert confidence == "high"
    assert why is None  # the low IP edge's why must not leak onto the high aggregate
    assert factors == [{"factor": "ioc_type", "value": "HASH", "reason": "Hash-type indicator"}]


def test_campaign_attribution_conflict_updates_why_not_higher(tmp_path, monkeypatch):
    """Gemini review on PR #489: an attribution conflict downgrades confidence
    but previously left why_not_higher stale (None), breaking the documented
    'why_not_higher equals the last factor's reason' contract."""
    async def run():
        db_path = str(tmp_path / "corr-conflict-why.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            pulses = [
                {
                    "pulse_id": "pulse-conflict-why",
                    "pulse_name": "Conflict wave",
                    "author": "analyst1",
                    "created_date": "2024-01-10",
                    "adversary": "Totally Different Threat Group",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses)
            await replace_otx_cve_pulses(db, "CVE-2024-HUB1", pulses)
            await db.commit()
            await db.execute(
                "INSERT INTO correlation_actor (cve_id, actor_name, confidence) VALUES (?, ?, ?)",
                ("CVE-2024-1001", "APT28", "medium"),
            )
            await db.commit()

            await build_campaigns_from_pulses(db)
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert len(campaigns) == 1
            assert campaigns[0]["attribution_conflict"] is True
            assert campaigns[0]["why_not_higher"] == "Adversary attribution conflicts with MITRE technique-matched actors"
            assert campaigns[0]["confidence_factors"][-1]["reason"] == campaigns[0]["why_not_higher"]
        finally:
            await db.close()

    run_db_test(run())


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

    run_db_test(run())


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

    run_db_test(run())


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

    run_db_test(run())


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
    actor = next(c for c in priority["components"] if c["signal"] == "actor")
    assert "threat intel link" not in actor["sentence"].lower()
    assert "historically associated" in actor["sentence"].lower()
    assert "verify relevance" in actor["sentence"].lower()

    empty = compute_correlation_priority({})
    assert empty == {"score": 0, "components": []}


def test_campaign_priority_booster_bonus_is_capped():
    from correlation.priority import compute_correlation_priority, CAP_CAMPAIGN

    boosted = compute_correlation_priority({
        "campaigns": [{"confidence": "high", "label": "X", "boosters": {"kev": ["CVE-1"]}}],
    })
    campaign_component = next(c for c in boosted["components"] if c["signal"] == "campaign")
    assert campaign_component["points"] == CAP_CAMPAIGN  # already at fraction 1.0, bonus capped
    assert "KEV-listed" in campaign_component["sentence"]


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

    run_db_test(run())


def test_mitre_overlap_ranks_strong_actor_match_above_weak(tmp_path, monkeypatch):
    """A group sharing all of the CVE's techniques should outrank one sharing
    only a sliver — overlap%, not 'any shared technique'."""
    from correlation.engine import find_actor_sector_correlation

    async def run():
        db_path = str(tmp_path / "corr-mitre.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            await db.execute(
                "INSERT INTO mitre_techniques (technique_id, name, url) VALUES "
                "('T1001', 'T1001', 'https://attack.mitre.org/T1001'), "
                "('T1002', 'T1002', 'https://attack.mitre.org/T1002'), "
                "('T1003', 'T1003', 'https://attack.mitre.org/T1003')"
            )
            await db.execute(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES "
                "('CVE-2024-1001', 'T1001'), ('CVE-2024-1001', 'T1002'), "
                "('CVE-2024-1001', 'T1003')"
            )
            await db.execute(
                "INSERT INTO mitre_groups (group_id, name, sectors) VALUES "
                "('G1', 'Strong Group', '[]'), ('G2', 'Weak Group', '[]')"
            )
            await db.execute(
                "INSERT INTO group_technique_map (group_id, technique_id) VALUES "
                "('G1', 'T1001'), ('G1', 'T1002'), ('G1', 'T1003'), ('G2', 'T1001')"
            )
            await db.commit()

            results = await find_actor_sector_correlation(db, "CVE-2024-1001")
            by_name = {r["actor_name"]: r for r in results}
            assert by_name["Strong Group"]["technique_overlap"] == 1.0
            assert by_name["Strong Group"]["confidence"] == "medium"
            assert round(by_name["Weak Group"]["technique_overlap"], 2) == 0.33
            assert by_name["Weak Group"]["confidence"] == "low"
            assert results[0]["actor_name"] == "Strong Group"
        finally:
            await db.close()

    run_db_test(run())


def test_mitre_overlap_below_threshold_is_excluded(tmp_path, monkeypatch):
    from correlation.engine import find_actor_sector_correlation

    async def run():
        db_path = str(tmp_path / "corr-mitre-min.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            await db.execute(
                "INSERT INTO mitre_techniques (technique_id, name, url) VALUES "
                "('T1001', 'T1001', 'https://attack.mitre.org/T1001'), "
                "('T1002', 'T1002', 'https://attack.mitre.org/T1002'), "
                "('T1003', 'T1003', 'https://attack.mitre.org/T1003'), "
                "('T1004', 'T1004', 'https://attack.mitre.org/T1004'), "
                "('T1005', 'T1005', 'https://attack.mitre.org/T1005')"
            )
            await db.execute(
                "INSERT INTO cve_technique_map (cve_id, technique_id) VALUES "
                "('CVE-2024-1001', 'T1001'), ('CVE-2024-1001', 'T1002'), "
                "('CVE-2024-1001', 'T1003'), ('CVE-2024-1001', 'T1004'), "
                "('CVE-2024-1001', 'T1005')"
            )
            await db.execute(
                "INSERT INTO mitre_groups (group_id, name, sectors) VALUES ('G3', 'Sliver Group', '[]')"
            )
            await db.execute(
                "INSERT INTO group_technique_map (group_id, technique_id) VALUES ('G3', 'T1001')"
            )
            await db.commit()

            results = await find_actor_sector_correlation(db, "CVE-2024-1001")
            assert "Sliver Group" not in {r["actor_name"] for r in results}
        finally:
            await db.close()

    run_db_test(run())


def test_kev_booster_affects_priority_not_confidence(tmp_path, monkeypatch):
    """CORR-PR-4: KEV/exploit status among campaign peers is a priority
    (urgency) signal, not a confidence signal -- a KEV-listed peer doesn't
    make the shared-pulse *link* itself more certain, so it must no longer
    bump campaign confidence. It still surfaces as evidence and now bumps
    the correlation priority score instead (priority.py)."""
    from correlation.priority import compute_correlation_priority

    async def run():
        db_path = str(tmp_path / "corr-booster.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            pulses = [
                {
                    "pulse_id": "pulse-kev-booster",
                    "pulse_name": "KEV-linked wave",
                    "author": "analyst1",
                    "created_date": "2024-01-10",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-1001", pulses)
            await replace_otx_cve_pulses(db, "CVE-2024-HUB1", pulses)
            await db.commit()

            await build_campaigns_from_pulses(db)
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-1001")
            assert len(campaigns) == 1
            assert campaigns[0]["boosters"]["kev"] == ["CVE-2024-HUB1"]
            # No strong (hash/domain) shared indicators here -- confidence
            # stays at the same-pulse co-tag base, unmoved by the KEV peer.
            assert campaigns[0]["confidence"] == "medium"

            with_booster = compute_correlation_priority({"campaigns": campaigns})
            without_booster = compute_correlation_priority(
                {"campaigns": [{**campaigns[0], "boosters": {"kev": [], "exploit": []}}]}
            )
            assert with_booster["score"] > without_booster["score"]
        finally:
            await db.close()

    run_db_test(run())


def test_temporal_anomaly_gated_off_stack_without_signal(tmp_path, monkeypatch):
    """§15: a vendor spike should be hidden for an unrelated, non-KEV CVE
    when a stack is configured, but shown for a KEV/exploit CVE regardless."""
    from auth.repo import create_user
    from correlation.engine import _get_temporal_for_cve, _store_temporal_anomalies
    from preferences.repo import upsert_user_stack

    async def run():
        db_path = str(tmp_path / "corr-temporal-gate.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        # Env would match acme:widget if still used as the matcher; admin My Stack must win.
        monkeypatch.setenv("BRIEFR_STACK_TERMS", "acme")
        db = await _seed_db(db_path)
        try:
            user = await create_user(db, "ops", "correct-horse-battery", role="admin")
            await upsert_user_stack(db, user["id"], "nginx")
            await db.commit()
            await db.execute(
                "UPDATE cves SET affected_products = '[\"acme:widget\"]' "
                "WHERE cve_id = 'CVE-2024-1001'"
            )
            await db.execute(
                "UPDATE cves SET affected_products = '[\"acme:widget\"]', is_kev = 1 "
                "WHERE cve_id = 'CVE-2024-HUB1'"
            )
            await db.commit()
            await _store_temporal_anomalies(db, [{
                "vendor": "acme",
                "current_week_count": 9,
                "average_weekly_count": 1.0,
                "anomaly_score": 9.0,
            }])
            await db.commit()

            off_stack_no_signal = await _get_temporal_for_cve(db, "CVE-2024-1001")
            assert off_stack_no_signal == []

            on_kev = await _get_temporal_for_cve(db, "CVE-2024-HUB1")
            assert len(on_kev) == 1
            assert on_kev[0]["vendor"] == "acme"
        finally:
            await db.close()

    run_db_test(run())


def test_stack_terms_list_uses_admin_my_stack_not_env(tmp_path, monkeypatch):
    from auth.repo import create_user
    from correlation.local import stack_terms_list
    from preferences.repo import upsert_user_stack

    async def run():
        db_path = str(tmp_path / "corr-stack-terms.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        monkeypatch.setenv("BRIEFR_STACK_TERMS", "env-only")
        db = await _seed_db(db_path)
        try:
            user = await create_user(db, "ops", "correct-horse-battery", role="admin")
            await upsert_user_stack(db, user["id"], "nginx")
            await db.commit()
            assert await stack_terms_list(db) == ["nginx"]
        finally:
            await db.close()

    run_db_test(run())


def test_rebuild_ioc_degree_counts_distinct_cves_and_pulses(tmp_path, monkeypatch):
    """CORR-PR-3: ioc_degree.cve_count must count distinct CVEs sharing an
    IOC, not raw row occurrences (a CVE linked via 2 pulses to the same IOC
    must count once, not twice)."""
    from db.correlation import rebuild_ioc_degree

    async def run():
        db_path = str(tmp_path / "corr-degree.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        db = await _seed_db(db_path)
        try:
            # Hub IOC shared across many distinct CVEs (high degree) vs a
            # rare IOC shared by exactly one CVE.
            for i in range(5):
                cve = f"CVE-2024-DEG{i}"
                pulse_id = f"pulse-deg-{i}"
                await replace_otx_cve_pulses(db, cve, [{
                    "pulse_id": pulse_id, "pulse_name": f"Pulse {i}", "author": "a",
                    "created_date": "2024-01-01", "adversary": "", "malware_families": [],
                    "tags": [], "targeted_countries": [], "ioc_count": 0,
                }])
                await replace_otx_pulse_iocs(db, pulse_id, [
                    {"ioc_type": "IP", "ioc_value": "203.0.113.1", "description": ""},
                ])
            await replace_otx_cve_pulses(db, "CVE-2024-RARE", [{
                "pulse_id": "pulse-rare", "pulse_name": "Rare", "author": "a",
                "created_date": "2024-01-01", "adversary": "", "malware_families": [],
                "tags": [], "targeted_countries": [], "ioc_count": 0,
            }])
            await replace_otx_pulse_iocs(db, "pulse-rare", [
                {"ioc_type": "DOMAIN", "ioc_value": "rare-actor.example", "description": ""},
            ])
            await db.commit()

            n = await rebuild_ioc_degree(db)
            assert n >= 2  # plus whatever _seed_db's own baseline IOCs contribute

            rows = {
                (r["ioc_type"], r["ioc_value"]): r
                for r in await db.execute_fetchall("SELECT * FROM ioc_degree")
            }
            hub = rows[("IP", "203.0.113.1")]
            assert hub["cve_count"] == 5
            rare = rows[("DOMAIN", "rare-actor.example")]
            assert rare["cve_count"] == 1
        finally:
            await db.close()

    run_db_test(run())
