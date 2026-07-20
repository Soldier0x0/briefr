"""Regression tests for Gemini review reconciliation (PRs #306–#385)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db, upsert_cve
from routers.cves import (
    _build_cve_filters,
    _circl_enrichment_patch,
    _detail_enrich_circl,
    _detail_enrich_exploits,
    _detail_enrich_otx,
)
from tests.conftest import run_db_test

CVE_MIXED = "cve-2024-mix1"


def test_build_cve_filters_search_uses_lower_for_trgm_alignment():
    conditions, params, _ = _build_cve_filters(
        severity=None,
        kev_only=False,
        kev_overdue_only=False,
        poc_only=False,
        patch_only=False,
        epss_min=None,
        search="Apache",
        stack=None,
        vendors=None,
        watchlist_only=False,
        hide_snoozed=False,
    )
    joined = " ".join(conditions)
    assert "LOWER(c.description)" in joined
    assert "LOWER(c.summary)" in joined
    assert "%apache%" in params


def test_circl_enrichment_patch_returns_only_owned_fields():
    enriched = {
        "cve_id": "CVE-2024-0001",
        "summary": "stale summary",
        "circl": {"capec_ids": ["CAPEC-1"], "extra_reference_count": 1},
        "capec_ids": ["CAPEC-1"],
        "source_urls": ["https://example.com/ref"],
    }
    patch = _circl_enrichment_patch(enriched)
    assert set(patch.keys()) == {"circl", "capec_ids", "source_urls"}
    assert "summary" not in patch


def test_circl_patch_merge_preserves_osv_summary():
    osv_patch = {"summary": "from-osv", "osv_packages": []}
    circl_patch = _circl_enrichment_patch(
        {"cve_id": "CVE-2024-0001", "summary": "stale-from-circl", "circl": {"capec_ids": []}}
    )
    cve = {"cve_id": "CVE-2024-0001", "summary": ""}
    cve.update(osv_patch)
    cve.update(circl_patch)
    assert cve["summary"] == "from-osv"


def test_circl_enrichment_patch_empty_dict_returns_empty_patch():
    assert _circl_enrichment_patch({}) == {}


def test_circl_enrichment_patch_none_returns_empty():
    assert _circl_enrichment_patch(None) == {}


def test_circl_enrichment_patch_non_dict_returns_empty():
    assert _circl_enrichment_patch("invalid") == {}
    assert _circl_enrichment_patch([]) == {}


def test_detail_enrich_otx_rolls_back_on_failure():
    db = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.load_otx_pulses_for_cve",
                AsyncMock(side_effect=RuntimeError("otx db fail")),
            ):
                result = await _detail_enrich_otx("CVE-2024-0001", "otx-key")
        assert result == {"otx_pulses": []}
        db.rollback.assert_awaited_once()
        db.close.assert_awaited_once()

    asyncio.run(_run())


def test_detail_enrich_otx_rollback_failure_still_returns_empty():
    db = AsyncMock()
    db.rollback = AsyncMock(side_effect=RuntimeError("rollback failed"))
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.load_otx_pulses_for_cve",
                AsyncMock(side_effect=RuntimeError("otx db fail")),
            ):
                result = await _detail_enrich_otx("CVE-2024-0001", "otx-key")
        assert result == {"otx_pulses": []}
        db.close.assert_awaited_once()

    asyncio.run(_run())


def test_detail_enrich_circl_rolls_back_on_failure():
    db = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.enrich_cve_circl",
                AsyncMock(side_effect=RuntimeError("circl db fail")),
            ):
                result = await _detail_enrich_circl({"cve_id": "CVE-2024-0001"})
        assert result == {}
        db.rollback.assert_awaited_once()
        db.close.assert_awaited_once()

    asyncio.run(_run())


def test_detail_enrich_circl_rollback_failure_still_returns_empty():
    db = AsyncMock()
    db.rollback = AsyncMock(side_effect=RuntimeError("rollback failed"))
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.enrich_cve_circl",
                AsyncMock(side_effect=RuntimeError("circl db fail")),
            ):
                result = await _detail_enrich_circl({"cve_id": "CVE-2024-0001"})
        assert result == {}
        db.close.assert_awaited_once()

    asyncio.run(_run())


def test_detail_enrich_circl_non_dict_result_returns_empty_patch():
    db = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.enrich_cve_circl",
                AsyncMock(return_value=None),
            ):
                result = await _detail_enrich_circl({"cve_id": "CVE-2024-0001"})
        assert result == {}
        db.commit.assert_awaited_once()

    asyncio.run(_run())


def test_detail_enrich_exploits_rolls_back_on_failure():
    db = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.commit = AsyncMock()

    async def _run():
        with patch("routers.cves.detail.get_db", AsyncMock(return_value=db)):
            with patch(
                "routers.cves.detail.load_public_exploits_for_cve",
                AsyncMock(side_effect=RuntimeError("sploitus fail")),
            ):
                with patch(
                    "routers.cves.detail.derive_exploit_provenance",
                    AsyncMock(return_value={"status": "pending", "source": "x", "as_of": None}),
                ):
                    result = await _detail_enrich_exploits(
                        "CVE-2024-0001", {"has_poc": False, "source_urls": []}
                    )
        assert result["public_exploits"] == []
        db.rollback.assert_awaited_once()

    asyncio.run(_run())


def test_upsert_cve_canonicalizes_mixed_case_id(tmp_path, monkeypatch):
    db_path = tmp_path / "cve_case.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(
                db,
                {
                    "cve_id": CVE_MIXED,
                    "description": "case test",
                    "severity": "LOW",
                },
            )
            await db.commit()
            row = await db.execute_fetchall(
                "SELECT cve_id FROM cves WHERE cve_id = ?",
                (CVE_MIXED.upper(),),
            )
            assert len(row) == 1
            assert row[0]["cve_id"] == CVE_MIXED.upper()
        finally:
            await db.close()

    run_db_test(_run())

