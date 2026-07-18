"""Embeddings E3 — related ANN + hybrid search API."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db
from db.embeddings_search import (
    build_hybrid_results,
    classify_query_shape,
    find_similar_via_embeddings_table,
    keyword_search_cves,
    rrf_merge,
)
from db.embeddings_store import upsert_cve_embedding_row
from ml.embeddings import find_similar_cves, l2_normalize, vector_to_blob
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


def test_classify_query_shape():
    assert classify_query_shape("CVE-2024-1234") == "cve_id"
    assert classify_query_shape("  cve-2024-99999  ") == "cve_id"
    assert classify_query_shape("openssl") == "short"
    assert classify_query_shape("remote code") == "short"
    assert classify_query_shape("sql injection in apache http server") == "long"


def test_rrf_merge_prefers_consensus():
    merged = rrf_merge(
        [["A", "B", "C"], ["B", "A", "D"]],
        limit=3,
    )
    ids = [cid for cid, _score in merged]
    assert ids[0] in ("A", "B")
    assert "C" in ids or "D" in ids


def test_build_hybrid_results_keyword_fallback():
    results, method = build_hybrid_results(
        keyword_rows=[
            {
                "cve_id": "CVE-2024-1",
                "description": "x",
                "summary": "",
                "cvss_score": 9.0,
                "severity": "CRITICAL",
                "published": "2024-01-01",
                "epss_score": 0.1,
                "is_kev": 0,
            }
        ],
        vector_hits=[],
        cards_by_id={
            "CVE-2024-1": {
                "cve_id": "CVE-2024-1",
                "description": "x",
                "summary": "",
                "cvss_score": 9.0,
                "severity": "CRITICAL",
                "published": "2024-01-01",
                "epss_score": 0.1,
                "is_kev": 0,
            }
        },
        limit=5,
        query_shape="long",
        mode="hybrid",
    )
    assert method == "keyword_fallback"
    assert results[0]["match_reasons"] == ["keyword"]


def test_related_prefers_embeddings_table(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e3rel.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            for cve_id, desc, vec in [
                ("CVE-2024-E3A", "Alpha RCE", [1.0, 0.0]),
                ("CVE-2024-E3B", "Beta distant", [0.0, 1.0]),
                ("CVE-2024-E3C", "Alpha twin", [0.99, 0.01]),
            ]:
                await db.execute(
                    "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                    (cve_id, desc, today),
                )
                blob = vector_to_blob(l2_normalize(np.array(vec, dtype="<f4")))
                await upsert_cve_embedding_row(
                    db, cve_id, MODEL, 2, blob, "hash-" + cve_id
                )
            await db.commit()
            via_table = await find_similar_via_embeddings_table(
                db, "CVE-2024-E3A", MODEL, limit=2
            )
            via_api = await find_similar_cves(db, "CVE-2024-E3A", limit=2)
            return via_table, via_api
        finally:
            await db.close()

    via_table, via_api = run_db_test(run())
    assert via_table is not None
    assert via_table[0]["cve_id"] == "CVE-2024-E3C"
    assert via_api[0]["cve_id"] == "CVE-2024-E3C"


def test_keyword_search_cves(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e3kw.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-KW1", "OpenSSL buffer overflow", today),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-KW2", "unrelated nginx issue", today),
            )
            await db.commit()
            hits = await keyword_search_cves(db, "openssl", limit=10)
            exact = await keyword_search_cves(db, "CVE-2024-KW1", limit=10)
            return hits, exact
        finally:
            await db.close()

    hits, exact = run_db_test(run())
    assert [h["cve_id"] for h in hits] == ["CVE-2024-KW1"]
    assert exact[0]["cve_id"] == "CVE-2024-KW1"


@pytest.fixture
def search_client(tmp_path, monkeypatch):
    db_path = tmp_path / "e3search.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")

    async def seed():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, published, affected_products)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-SRCH",
                    "Critical SQL injection in ACME widget",
                    "CRITICAL",
                    today,
                    json.dumps(["acme:widget"]),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        yield client


def test_search_semantic_keyword_mode(search_client):
    body = search_client.get(
        "/api/search/semantic",
        params={"q": "SQL injection", "mode": "keyword", "limit": 10},
    ).json()
    assert body["meta"]["mode_requested"] == "keyword"
    assert body["meta"]["method"] in ("keyword", "keyword_first")
    assert any(r["cve_id"] == "CVE-2024-SRCH" for r in body["data"])
    assert "keyword" in body["data"][0]["match_reasons"]


def test_search_semantic_hybrid_falls_back_without_embeddings(search_client):
    body = search_client.get(
        "/api/search/semantic",
        params={"q": "ACME widget", "mode": "hybrid"},
    ).json()
    assert body["meta"]["embeddings_enabled"] is False
    assert body["meta"]["method"] == "keyword_fallback"
    assert body["data"]
    assert body["data"][0]["cve_id"] == "CVE-2024-SRCH"


def test_search_rejects_bad_mode(search_client):
    res = search_client.get(
        "/api/search/semantic", params={"q": "x", "mode": "magic"}
    )
    assert res.status_code == 400
