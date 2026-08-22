"""Regression tests for IOC value digest indexing (PostgreSQL btree row-size limit)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.ioc_digest import ioc_value_digest
from db.ti_mirror import upsert_ti_mirror_iocs
import database
from database import init_db
from tests.conftest import run_db_test


def _oversized_phish_url() -> str:
    """Canonical URL whose indexed (ioc_type, ioc_value) row exceeds PG btree limits."""
    host = "evil.example"
    path = "a" * 2900
    return f"https://{host}/{path}"


def test_ioc_value_digest_preserves_url_path_case():
    upper = ioc_value_digest("https://evil.example/A")
    lower = ioc_value_digest("https://evil.example/a")
    assert upper != lower


def test_ioc_value_digest_is_fixed_width():
    short = ioc_value_digest("https://evil.example/a")
    long = ioc_value_digest(_oversized_phish_url())
    assert len(short) == 32
    assert len(long) == 32
    assert short != long


def test_retro_match_ignores_cross_type_digest_collision(tmp_path, monkeypatch):
    """Same value under different IOC types must not retro-match OTX."""
    async def run():
        db_path = str(tmp_path / "retro-type.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role)
                VALUES (1, 'pytest-admin', 'hash', 'admin')
                """
            )
            await db.execute(
                """
                INSERT INTO ioc_watchlist (user_id, ioc_type, ioc_value, label)
                VALUES (1, 'domain', 'shared.example', 'watch')
                """
            )
            await db.execute(
                """
                INSERT INTO otx_pulse_iocs (pulse_id, ioc_type, ioc_value, description)
                VALUES ('p-cross', 'IPv4', 'shared.example', 'ip row')
                """
            )
            await db.commit()
            from ioc.retro_match import find_retro_matches

            matches = await find_retro_matches(db)
            assert not any(m.get("source") == "otx" for m in matches)
        finally:
            await db.close()

    run_db_test(run())


def test_upsert_ti_mirror_accepts_oversized_url(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "oversized-mirror.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await database.get_db()
        try:
            url = _oversized_phish_url()
            written = await upsert_ti_mirror_iocs(
                db,
                "phishtank",
                [
                    {
                        "ref_id": "phish-oversized-1",
                        "ioc_type": "url",
                        "ioc_value": url,
                        "raw_ioc": url,
                        "host_ioc": "evil.example",
                        "threat_type": "phishing",
                        "confidence_level": "100",
                    }
                ],
            )
            await db.commit()
            assert written == 1
            rows = await db.execute_fetchall(
                """
                SELECT ioc_value, ioc_value_digest
                FROM ti_mirror_iocs
                WHERE source = 'phishtank' AND ref_id = 'phish-oversized-1'
                """
            )
            assert len(rows) == 1
            row = rows[0]
            assert len(row["ioc_value"]) > 2700
            assert row["ioc_value_digest"] == ioc_value_digest(url)
        finally:
            await db.close()

    run_db_test(run())


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not PostgreSQL",
)
def test_upsert_ti_mirror_oversized_url_on_postgres(monkeypatch):
    """Postgres-only: verifies btree index maintenance on digest, not raw URL."""

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            url = _oversized_phish_url()
            ref_id = "phish-pg-oversized"
            await upsert_ti_mirror_iocs(
                db,
                "phishtank",
                [
                    {
                        "ref_id": ref_id,
                        "ioc_type": "url",
                        "ioc_value": url,
                        "raw_ioc": url,
                        "host_ioc": "evil.example",
                        "threat_type": "phishing",
                        "confidence_level": "100",
                    }
                ],
            )
            await db.commit()
            hits = await db.execute_fetchall(
                """
                SELECT 1 AS ok FROM ti_mirror_iocs
                WHERE source = 'phishtank'
                  AND ref_id = ?
                  AND ioc_value_digest = ?
                """,
                (ref_id, ioc_value_digest(url)),
            )
            assert hits
            await db.execute(
                "DELETE FROM ti_mirror_iocs WHERE source = 'phishtank' AND ref_id = ?",
                (ref_id,),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())
