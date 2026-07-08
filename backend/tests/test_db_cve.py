"""Postgres-native cve module (Post-B Phase 1)."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.cve as cve_mod
from db.config import is_postgres
from db.cve import (
    _insert_cve_changes_batch,
    cve_exists,
    delete_cves_by_ids,
    get_cve_summaries_by_ids,
    get_cves_for_llm_product_extraction,
    get_related_cves,
    purge_legacy_rejected_cves,
    set_llm_affected_products,
    upsert_cve,
    upsert_cve_embedding,
    upsert_cves,
)
from database import get_db, init_db
from tests.conftest import run_db_test

CVE_A = "CVE-2024-5001"
CVE_B = "CVE-2024-5002"
CVE_C = "CVE-2024-5003"


def test_cve_sql_uses_native_placeholders():
    assert "$1" in cve_mod._CVE_EXISTS_PG
    assert "$17" in cve_mod._UPSERT_CVE_PG
    assert "ON CONFLICT(cve_id)" in cve_mod._UPSERT_CVE_PG
    assert "?" in cve_mod._CVE_EXISTS_SQLITE
    assert "ON CONFLICT(cve_id)" in cve_mod._UPSERT_CVE_SQLITE
    assert "$5" in cve_mod._INSERT_CVE_CHANGE_PG
    assert "$2" in cve_mod._GET_CVES_FOR_LLM_PG


def test_upsert_cves_and_exists_round_trip(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_upsert.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await cve_exists(db, CVE_A) is False
            await upsert_cves(
                db,
                [
                    {
                        "cve_id": CVE_A,
                        "description": "first",
                        "severity": "HIGH",
                        "cvss_score": 8.0,
                        "affected_products": ["vendor:product"],
                    }
                ],
            )
            await db.commit()
            assert await cve_exists(db, CVE_A) is True

            await upsert_cves(
                db,
                [
                    {
                        "cve_id": CVE_A,
                        "description": "updated",
                        "severity": "CRITICAL",
                        "cvss_score": 9.5,
                    }
                ],
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT description, cvss_score FROM cves WHERE cve_id = ?"
                if not is_postgres()
                else "SELECT description, cvss_score FROM cves WHERE cve_id = $1",
                (CVE_A,),
            )
            assert rows[0]["description"] == "updated"
            assert float(rows[0]["cvss_score"]) == 9.5
        finally:
            await db.close()

    run_db_test(_run())


def test_insert_cve_changes_batch(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_changes.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(db, {"cve_id": CVE_A, "description": "x"})
            await _insert_cve_changes_batch(
                db, [(CVE_A, "has_poc", "0", "1")]
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT field_name, new_value FROM cve_change_history WHERE cve_id = ?"
                if not is_postgres()
                else "SELECT field_name, new_value FROM cve_change_history WHERE cve_id = $1",
                (CVE_A,),
            )
            assert len(rows) == 1
            assert rows[0]["field_name"] == "has_poc"
        finally:
            await db.close()

    run_db_test(_run())


def test_delete_and_purge_rejected(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_delete.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(db, {"cve_id": CVE_A, "description": "Rejected reason: spam"})
            await upsert_cve(db, {"cve_id": CVE_B, "description": "valid"})
            await db.commit()

            purged = await purge_legacy_rejected_cves(db)
            await db.commit()
            assert purged == 1
            assert await cve_exists(db, CVE_B) is True
            assert await cve_exists(db, CVE_A) is False

            await upsert_cve(db, {"cve_id": CVE_C, "description": "to delete"})
            await db.commit()
            deleted = await delete_cves_by_ids(db, [CVE_C])
            await db.commit()
            assert deleted == 1
            assert await cve_exists(db, CVE_C) is False
        finally:
            await db.close()

    run_db_test(_run())


def test_get_related_cves_by_product(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_related.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            recent = (date.today() - timedelta(days=5)).isoformat()
            old = (date.today() - timedelta(days=60)).isoformat()
            for cve_id, published in ((CVE_A, recent), (CVE_B, recent), (CVE_C, old)):
                await upsert_cve(
                    db,
                    {
                        "cve_id": cve_id,
                        "description": f"desc {cve_id}",
                        "published": published,
                        "affected_products": ["acme:widget"],
                        "cvss_score": 7.0,
                    },
                )
            await db.commit()

            related = await get_related_cves(db, CVE_A, limit=5)
            ids = {r["cve_id"] for r in related}
            assert CVE_B in ids
            assert CVE_C not in ids
            assert CVE_A not in ids
        finally:
            await db.close()

    run_db_test(_run())


def test_embedding_and_summaries(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_embed.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(
                db,
                {
                    "cve_id": CVE_A,
                    "description": "embed me",
                    "severity": "MEDIUM",
                    "published": "2024-01-01",
                },
            )
            await db.commit()
            blob = b"\x00\x00\x80\x3f"
            await upsert_cve_embedding(db, CVE_A, "test-model", 1, blob)
            await db.commit()

            summaries = await get_cve_summaries_by_ids(db, [CVE_A, CVE_B])
            assert CVE_A in summaries
            assert summaries[CVE_A]["severity"] == "MEDIUM"
        finally:
            await db.close()

    run_db_test(_run())


def test_set_llm_affected_products_only_when_empty(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_llm.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(
                db,
                {
                    "cve_id": CVE_A,
                    "description": "no products yet",
                    "affected_products": [],
                },
            )
            await db.commit()
            assert await set_llm_affected_products(db, CVE_A, ["llm:vendor"]) is True
            await db.commit()
            assert await set_llm_affected_products(db, CVE_A, ["other:vendor"]) is False

            rows = await db.execute_fetchall(
                "SELECT affected_products, affected_products_source FROM cves WHERE cve_id = ?"
                if not is_postgres()
                else "SELECT affected_products, affected_products_source FROM cves WHERE cve_id = $1",
                (CVE_A,),
            )
            assert "llm:vendor" in rows[0]["affected_products"]
            assert rows[0]["affected_products_source"] == "llm"
        finally:
            await db.close()

    run_db_test(_run())


def test_get_cves_for_llm_product_extraction(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "cve_llm_pick.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cve(
                db,
                {"cve_id": CVE_A, "description": "needs llm", "affected_products": []},
            )
            await upsert_cve(
                db,
                {
                    "cve_id": CVE_B,
                    "description": "has products",
                    "affected_products": ["vendor:prod"],
                },
            )
            await db.commit()

            picked = await get_cves_for_llm_product_extraction(db, limit=10)
            ids = [r["cve_id"] for r in picked]
            assert CVE_A in ids
            assert CVE_B not in ids
        finally:
            await db.close()

    run_db_test(_run())
