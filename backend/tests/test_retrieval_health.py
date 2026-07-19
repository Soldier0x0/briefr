"""Retrieval ops health + auto-on-ingest defaults / coupling (RH-1/RH-2)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db
from db.embeddings_pgvector import ENTITY_TYPE_CVE
from db.embeddings_store import count_embeddings_by_entity, upsert_cve_embedding_row
from ml.embeddings import l2_normalize, vector_to_blob
from routers import admin as admin_router
from services.retrieval_health import build_retrieval_health
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "retrieval_health_admin.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _noop_async(*args, **kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


def test_count_embeddings_by_entity(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite count path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "rh_count.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            vec = l2_normalize(np.array([1.0, 0.0, 0.0], dtype="<f4"))
            blob = vector_to_blob(vec)
            await upsert_cve_embedding_row(
                db, "CVE-2024-RH1", MODEL, 3, blob, "a" * 64
            )
            await db.commit()
            counts = await count_embeddings_by_entity(db, MODEL)
            assert counts[ENTITY_TYPE_CVE] == 1
            assert counts["technique"] == 0
            assert counts["campaign"] == 0
            assert counts["total"] == 1
        finally:
            await db.close()

    run_db_test(run())


def test_build_retrieval_health_disabled(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite health path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "rh_health.db"))
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    monkeypatch.delenv("EMBEDDINGS_AUTO_ON_INGEST", raising=False)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            payload = await build_retrieval_health(db)
            assert payload["embeddings_enabled"] is False
            assert payload["auto_on_ingest"] is False  # requires enabled
            assert payload["extension_vector"] == "n/a"
            assert payload["degraded"] == {"reason": "disabled"}
            assert "counts" in payload and "pending" in payload
            assert payload["pending"].get("includes_hash_drift") is False
            assert "last_ingest_tail" in payload
        finally:
            await db.close()

    run_db_test(run())


def test_pending_missing_is_cheap_sql_count(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite pending path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "rh_pending.db"))
    from db.embeddings_store import count_embeddings_pending_missing
    from datetime import date

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-PEND", "Needs embed", date.today().isoformat()),
            )
            await db.commit()
            pending = await count_embeddings_pending_missing(db, MODEL)
            assert pending["cve"] >= 1
            assert pending["includes_hash_drift"] == 0
        finally:
            await db.close()

    run_db_test(run())


def test_auto_on_ingest_defaults_on_when_enabled(monkeypatch):
    from ml import embeddings as emb

    monkeypatch.setenv("EMBEDDINGS_ENABLED", "1")
    monkeypatch.delenv("EMBEDDINGS_AUTO_ON_INGEST", raising=False)
    assert emb.embeddings_auto_on_ingest_enabled() is True
    monkeypatch.setenv("EMBEDDINGS_AUTO_ON_INGEST", "0")
    assert emb.embeddings_auto_on_ingest_enabled() is False


def test_couple_embeddings_auto_on_enable():
    couple = admin_router._couple_embeddings_auto_on_enable
    # off → on couples auto=1
    out = couple([("EMBEDDINGS_ENABLED", "1")], previous_enabled=False)
    assert ("EMBEDDINGS_AUTO_ON_INGEST", "1") in out
    # explicit auto=0 preserved
    out2 = couple(
        [("EMBEDDINGS_ENABLED", "1"), ("EMBEDDINGS_AUTO_ON_INGEST", "0")],
        previous_enabled=False,
    )
    assert ("EMBEDDINGS_AUTO_ON_INGEST", "0") in out2
    assert out2.count(("EMBEDDINGS_AUTO_ON_INGEST", "1")) == 0
    # already enabled — no couple
    out3 = couple([("EMBEDDINGS_ENABLED", "1")], previous_enabled=True)
    assert all(k != "EMBEDDINGS_AUTO_ON_INGEST" for k, _ in out3)


def test_admin_retrieval_health_endpoint(admin_client, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    res = admin_client.get("/api/admin/retrieval/health")
    assert res.status_code == 200
    body = res.json()
    assert body["embeddings_enabled"] is False
    assert body["degraded"]["reason"] == "disabled"
    assert "counts" in body
    assert "cve" in body["counts"]


def test_admin_ai_ops_overview_uses_live_count_key(admin_client):
    overview = admin_client.get("/api/admin/ai/operations/overview")
    assert overview.status_code == 200
    emb = overview.json()["features"]["embeddings"]
    assert "vector_count" in emb
    assert "legacy_cve_embeddings" in emb
    assert emb["label"].startswith("Embeddings index")


def test_config_enable_embeddings_couples_auto_on_ingest(admin_client, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    monkeypatch.setenv("EMBEDDINGS_AUTO_ON_INGEST", "0")
    res = admin_client.post(
        "/api/admin/config",
        json={"key": "EMBEDDINGS_ENABLED", "value": "1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "EMBEDDINGS_AUTO_ON_INGEST" in body.get("coupled_keys", [])
    assert os.environ.get("EMBEDDINGS_AUTO_ON_INGEST") == "1"
    assert os.environ.get("EMBEDDINGS_ENABLED") == "1"
