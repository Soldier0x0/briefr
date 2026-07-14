"""CORR-PR-11: alias-aware attribution conflict."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from correlation.attribution import (
    attribution_conflict,
    build_attribution_claims,
    build_alias_families,
)
from correlation.campaigns import build_campaigns_from_pulses, get_campaigns_for_cve
from database import init_db, replace_otx_cve_pulses
import database


def test_apt28_and_fancy_bear_are_not_a_conflict():
    index = build_alias_families([
        {
            "name": "APT28",
            "aliases": json.dumps(["Fancy Bear", "Sofacy", "Sednit"]),
        }
    ])
    assert attribution_conflict("Fancy Bear", ["APT28"], alias_index=index) is False
    assert build_attribution_claims("Fancy Bear", ["APT28"], alias_index=index) is None


def test_genuine_mismatch_surfaces_dual_claims():
    index = build_alias_families([
        {"name": "APT28", "aliases": json.dumps(["Fancy Bear"])}
    ])
    claims = build_attribution_claims(
        "Totally Different Group",
        ["APT28"],
        alias_index=index,
        otx_observed_at="2024-01-10",
    )
    assert claims is not None
    assert claims["status"] == "unresolved"
    assert len(claims["claims"]) == 2
    assert claims["claims"][0]["source"] == "otx"
    assert claims["claims"][1]["source"] == "mitre_technique"


def test_campaign_api_includes_attribution_claims_on_conflict(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "attr-conflict.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published)
                VALUES ('CVE-2024-9001', 'One', '2024-01-01'), ('CVE-2024-9002', 'Two', '2024-01-02')
                """
            )
            pulses = [
                {
                    "pulse_id": "pulse-attr",
                    "pulse_name": "Conflict wave",
                    "author": "analyst",
                    "created_date": "2024-01-10",
                    "adversary": "Evil Syndicate",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-9001", pulses)
            await replace_otx_cve_pulses(db, "CVE-2024-9002", pulses)
            await db.execute(
                """
                INSERT INTO mitre_groups (group_id, name, aliases)
                VALUES ('G99', 'APT28', '["Fancy Bear"]')
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_actor (cve_id, actor_name, confidence)
                VALUES ('CVE-2024-9001', 'APT28', 'medium')
                """
            )
            await build_campaigns_from_pulses(db)
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-9001")
            assert len(campaigns) == 1
            assert campaigns[0]["attribution_conflict"] is True
            assert campaigns[0]["attribution_claims"]["claims"][0]["value"] == "Evil Syndicate"
        finally:
            await db.close()

    run_db_test(run())


def test_fancy_bear_pulse_matches_apt28_mitre_actor(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "attr-alias.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published)
                VALUES ('CVE-2024-9101', 'One', '2024-01-01'), ('CVE-2024-9102', 'Two', '2024-01-02')
                """
            )
            pulses = [
                {
                    "pulse_id": "pulse-alias",
                    "pulse_name": "Alias test",
                    "author": "analyst",
                    "created_date": "2024-01-10",
                    "adversary": "Fancy Bear",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 0,
                }
            ]
            await replace_otx_cve_pulses(db, "CVE-2024-9101", pulses)
            await replace_otx_cve_pulses(db, "CVE-2024-9102", pulses)
            await db.execute(
                """
                INSERT INTO mitre_groups (group_id, name, aliases)
                VALUES ('G28', 'APT28', '["Fancy Bear", "Sofacy"]')
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_actor (cve_id, actor_name, confidence)
                VALUES ('CVE-2024-9101', 'APT28', 'medium')
                """
            )
            await build_campaigns_from_pulses(db)
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-9101")
            assert len(campaigns) == 1
            assert campaigns[0]["attribution_conflict"] is False
            assert campaigns[0]["attribution_claims"] is None
        finally:
            await db.close()

    run_db_test(run())
