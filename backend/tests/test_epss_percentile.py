"""Tests for EPSS percentile ingest (C2-R3)."""

import asyncio

from feeds.epss import _parse_epss_fields, fetch_epss_bulk


def test_parse_epss_fields_includes_percentile():
    parsed = _parse_epss_fields("0.42", "0.99100")
    assert parsed == {"score": 0.42, "percentile": 0.991}


def test_parse_epss_fields_without_percentile():
    parsed = _parse_epss_fields("0.42", None)
    assert parsed == {"score": 0.42, "percentile": None}


def test_update_epss_scores_stores_percentile(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings

    db_path = tmp_path / "epss_pct.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "db_path", str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)

    async def run():
        await db_module.init_db()
        db = await db_module.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, epss_score, epss_percentile)
                VALUES (?, ?, ?, ?)
                """,
                ("CVE-2024-9001", "test", 0.1, None),
            )
            await db.commit()

            await db_module.update_epss_scores(
                db,
                {"CVE-2024-9001": {"score": 0.2, "percentile": 0.95}},
            )
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT epss_score, epss_percentile FROM cves WHERE cve_id = ?",
                ("CVE-2024-9001",),
            )
            assert float(rows[0]["epss_score"]) == 0.2
            assert float(rows[0]["epss_percentile"]) == 0.95
        finally:
            await db.close()

    asyncio.run(run())


def test_fetch_epss_bulk_parses_percentile(monkeypatch):
    csv_body = (
        "#comment\n"
        "cve,epss,percentile\n"
        "CVE-2024-0001,0.12345,0.99000\n"
    )

    class FakeResponse:
        content = __import__("gzip").compress(csv_body.encode())

    async def fake_get(*_args, **_kwargs):
        return FakeResponse()

    async def fake_record(*_a, **_k):
        return None

    monkeypatch.setattr("feeds.epss.resilient_get", fake_get)
    monkeypatch.setattr("feeds.epss.record_api_call", fake_record)

    async def run():
        scores = await fetch_epss_bulk({"CVE-2024-0001"})
        assert scores["CVE-2024-0001"]["score"] == 0.12345
        assert scores["CVE-2024-0001"]["percentile"] == 0.99

    asyncio.run(run())
