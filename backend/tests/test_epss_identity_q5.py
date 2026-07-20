"""Q5 EPSS CSV file identity skip."""

from __future__ import annotations

import gzip
import io

from feeds.file_identity import (
    EPSS_FILE_IDENTITY_KEY,
    identity_matches,
    parse_epss_score_date,
    sha256_bytes,
)
from feeds.epss import parse_epss_csv_gz


def _sample_csv_gz(*, score_date: str = "2026-07-17", score: str = "0.12") -> bytes:
    text = (
        f"#model_version:v2025.03.01,score_date:{score_date}\n"
        "cve,epss,percentile\n"
        f"CVE-2024-0001,{score},0.90\n"
        f"CVE-2024-0002,0.01,0.10\n"
    )
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(text.encode("utf-8"))
    return buf.getvalue()


def test_parse_score_date_and_sha():
    raw = _sample_csv_gz()
    digest = sha256_bytes(raw)
    scores, score_date = parse_epss_csv_gz(raw, {"CVE-2024-0001"})
    assert score_date == "2026-07-17"
    assert "CVE-2024-0001" in scores
    assert parse_epss_score_date(
        gzip.decompress(raw).decode()
    ) == "2026-07-17"
    assert identity_matches({"sha256": digest, "score_date": score_date}, sha256=digest)
    assert not identity_matches({"sha256": "deadbeef"}, sha256=digest)


def test_identity_skip_in_sync(tmp_path, monkeypatch):
    db_path = tmp_path / "epss_id.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)

    raw = _sample_csv_gz()
    digest = sha256_bytes(raw)
    calls = {"n": 0}

    async def _dl():
        calls["n"] += 1
        return raw, digest

    monkeypatch.setattr("scheduler.download_epss_csv_gz", _dl)

    from database import get_db, init_db
    from db.cve import upsert_cves
    from feeds.file_identity import clear_file_identity, get_file_identity, set_file_identity
    from scheduler import _run_epss_sync
    from tests.conftest import run_db_test

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await upsert_cves(
                db,
                [
                    {
                        "cve_id": "CVE-2024-0001",
                        "description": "x",
                        "cvss_score": 5.0,
                        "severity": "MEDIUM",
                        "published": "2024-01-01T00:00:00",
                        "modified": "2024-01-01T00:00:00",
                        "affected_products": [],
                        "cwe_ids": [],
                        "source_urls": [],
                        "is_kev": 0,
                        "epss_score": None,
                        "has_poc": 0,
                        "patch_available": 0,
                    }
                ],
            )
            await set_file_identity(
                db, EPSS_FILE_IDENTITY_KEY, sha256=digest, score_date="2026-07-17"
            )
            await db.commit()
        finally:
            await db.close()

        updates = {"n": 0}

        async def _count_update(db, scores, commit_every=None):
            updates["n"] += 1
            from db.enrichment import update_epss_scores as _real

            return await _real(db, scores, commit_every=commit_every)

        monkeypatch.setattr("scheduler.update_epss_scores", _count_update)
        await _run_epss_sync()
        assert calls["n"] == 1
        assert updates["n"] == 0
        db = await get_db()
        try:
            ident = await get_file_identity(db, EPSS_FILE_IDENTITY_KEY)
            assert ident and ident["sha256"] == digest
            await clear_file_identity(db, EPSS_FILE_IDENTITY_KEY)
            await db.commit()
        finally:
            await db.close()

        await _run_epss_sync()
        assert calls["n"] == 2
        assert updates["n"] == 1
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT epss_score FROM cves WHERE cve_id = ?",
                ("CVE-2024-0001",),
            )
            score = dict(row[0]).get("epss_score")
            assert float(score) == 0.12
        finally:
            await db.close()

    run_db_test(_run())


def test_clear_file_identity(tmp_path, monkeypatch):
    db_path = tmp_path / "epss_clear.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)

    from database import get_db, init_db
    from feeds.file_identity import clear_file_identity, get_file_identity, set_file_identity
    from tests.conftest import run_db_test

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await set_file_identity(
                db, EPSS_FILE_IDENTITY_KEY, sha256="abc", score_date="2026-01-01"
            )
            await db.commit()
            await clear_file_identity(db, EPSS_FILE_IDENTITY_KEY)
            await db.commit()
            ident = await get_file_identity(db, EPSS_FILE_IDENTITY_KEY)
            assert not ident or not ident.get("sha256")
        finally:
            await db.close()

    run_db_test(_run())
