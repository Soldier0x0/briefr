"""CORR-PR-9: pulse families, campaign dedup, suppression migration, retraction."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from correlation.campaigns import (
    build_campaigns_from_pulses,
    campaign_id_for_pulse,
    get_campaigns_for_cve,
)
from correlation.clusters import list_correlation_clusters
from correlation.pulse_families import (
    campaign_id_for_family,
    family_id_for_oldest_pulse,
    legacy_campaign_id_for_pulse,
    normalize_pulse_name,
)
from correlation.suppressions import add_suppression
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database


def test_normalize_pulse_name_strips_part_suffix():
    assert normalize_pulse_name("Known_Cve | Part 1/2") == "known cve"
    assert normalize_pulse_name("Known_Cve | Part 2/2") == "known cve"
    assert normalize_pulse_name("Known_Cve | part 1/2") == normalize_pulse_name(
        "Known_Cve | PART 2/2"
    )


def test_normalize_pulse_name_strips_trailing_punctuation():
    assert normalize_pulse_name("Apache Struts RCE!") == "apache struts rce"
    assert normalize_pulse_name("Apache Struts RCE.") == "apache struts rce"
    assert normalize_pulse_name("Apache Struts RCE?") == "apache struts rce"
    assert normalize_pulse_name("Apache Struts RCE...!!") == "apache struts rce"


def test_normalize_pulse_name_underscores_to_spaces():
    assert normalize_pulse_name("Known_Cve") == "known cve"
    assert normalize_pulse_name("Foo__Bar___Baz") == "foo bar baz"


def test_normalize_pulse_name_identity_across_variants():
    """Part / punctuation / underscore variants share one matching identity."""
    variants = [
        "Known_Cve | Part 1/2",
        "known_cve | part 2/2",
        "Known Cve!",
        "Known_Cve.",
        "  Known__Cve  ",
    ]
    keys = {normalize_pulse_name(v) for v in variants}
    assert keys == {"known cve"}


async def _seed_cves(db) -> None:
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
        VALUES
            ('CVE-2024-2001', 'One', '2024-01-01', 0, 0, 0.1),
            ('CVE-2024-2002', 'Two', '2024-01-02', 0, 0, 0.2),
            ('CVE-2024-3001', 'Three', '2024-01-03', 0, 0, 0.3),
            ('CVE-2024-3002', 'Four', '2024-01-04', 0, 0, 0.4)
        """
    )


def _pulse(
    pulse_id: str,
    *,
    author: str,
    created_date: str,
    name: str = "Mirrored campaign",
) -> dict:
    return {
        "pulse_id": pulse_id,
        "pulse_name": name,
        "author": author,
        "created_date": created_date,
        "adversary": "APT-MIRROR",
        "malware_families": [],
        "tags": ["test"],
        "targeted_countries": [],
        "ioc_count": 0,
    }


async def _seed_mirrored_family(db) -> None:
    await _seed_cves(db)
    shared = [
        _pulse("pulse-mirror-a", author="author-one", created_date="2024-01-05"),
        _pulse("pulse-mirror-b", author="author-two", created_date="2024-01-15"),
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-2001", shared)
    await replace_otx_cve_pulses(db, "CVE-2024-2002", shared)


async def _seed_distinct_campaigns(db) -> None:
    await _seed_cves(db)
    family_a = [_pulse("pulse-distinct-a", author="a1", created_date="2024-02-01", name="Alpha")]
    family_b = [_pulse("pulse-distinct-b", author="b1", created_date="2024-02-02", name="Beta")]
    await replace_otx_cve_pulses(db, "CVE-2024-2001", family_a)
    await replace_otx_cve_pulses(db, "CVE-2024-2002", family_a)
    await replace_otx_cve_pulses(db, "CVE-2024-3001", family_b)
    await replace_otx_cve_pulses(db, "CVE-2024-3002", family_b)


def test_mirrored_pulses_collapse_to_one_campaign(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "fam-mirror.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_mirrored_family(db)
            stats = await build_campaigns_from_pulses(db)
            await db.commit()
            assert stats["campaigns"] == 1

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-2001")
            assert len(campaigns) == 1
            assert campaigns[0]["author_count"] == 2
            fam_id = family_id_for_oldest_pulse("pulse-mirror-a")
            assert campaigns[0]["family_id"] == fam_id
            assert campaigns[0]["campaign_id"] == campaign_id_for_family(
                fam_id, "pulse-mirror-a"
            )
        finally:
            await db.close()

    run_db_test(run())


def test_distinct_pulses_stay_separate_campaigns(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "fam-distinct.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_distinct_campaigns(db)
            stats = await build_campaigns_from_pulses(db)
            await db.commit()
            assert stats["campaigns"] == 2

            alpha = await get_campaigns_for_cve(db, "CVE-2024-2001")
            beta = await get_campaigns_for_cve(db, "CVE-2024-3001")
            assert len(alpha) == 1
            assert len(beta) == 1
            assert alpha[0]["campaign_id"] != beta[0]["campaign_id"]
        finally:
            await db.close()

    run_db_test(run())


def test_legacy_suppression_maps_to_family_campaign(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "fam-suppress.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_mirrored_family(db)
            await build_campaigns_from_pulses(db)
            await db.commit()

            legacy_b = legacy_campaign_id_for_pulse("pulse-mirror-b")
            await add_suppression(
                db,
                "CVE-2024-2001",
                "campaign_id",
                {"campaign_id": legacy_b},
            )
            await db.commit()

            campaigns = await get_campaigns_for_cve(db, "CVE-2024-2001")
            assert campaigns == []
        finally:
            await db.close()

    run_db_test(run())


def test_vanished_family_is_retracted_not_deleted(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "fam-retract.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_distinct_campaigns(db)
            await build_campaigns_from_pulses(db)
            await db.commit()

            beta_id = campaign_id_for_pulse("pulse-distinct-b")
            await db.execute(
                "DELETE FROM otx_cve_pulses WHERE pulse_id = 'pulse-distinct-b'"
            )
            await db.execute(
                "DELETE FROM otx_pulses WHERE pulse_id = 'pulse-distinct-b'"
            )
            await build_campaigns_from_pulses(db)
            await db.commit()

            row = await db.execute_fetchall(
                "SELECT retracted_at, lifecycle FROM correlation_campaigns WHERE campaign_id = ?",
                (beta_id,),
            )
            assert row
            assert row[0]["retracted_at"]
            assert row[0]["lifecycle"] == "declining"

            beta_live = await get_campaigns_for_cve(db, "CVE-2024-3001")
            assert beta_live == []

            clusters = await list_correlation_clusters(db, cve_id="CVE-2024-3001")
            assert clusters["clusters"] == []

            alpha = await get_campaigns_for_cve(db, "CVE-2024-2001")
            assert len(alpha) == 1
        finally:
            await db.close()

    run_db_test(run())
