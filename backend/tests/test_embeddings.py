"""Tests for CVE description embeddings (V1.3 Theme 7).

Covers: BLOB round-trip, the NumPy brute-force cosine path, the
embeddings-disabled default, the heuristic fallback on
GET /api/cves/{id}/related, and the scheduler backfill (with a fake model —
fastembed is never required for the test suite).
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db, init_db
import numpy as np
import pytest

import database
import ml.embeddings as emb
from db.config import is_postgres
from ml.embeddings import (
    blob_to_vector,
    embeddings_enabled,
    find_similar_cves,
    l2_normalize,
    run_embeddings_backfill,
    vector_to_blob,
)
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"

# _db_with_embeddings below builds a hand-rolled :memory: SQLite schema with
# a SQLite-specific column default (datetime('now')) — a standalone unit
# test of find_similar_cves() against a bespoke schema, not the app's
# dialect-aware db/ layer. Genuinely SQLite-only; portable rewrite is
# Post-B scope, not this CI-gate PR's (same call as test_wallboard.py).
_requires_sqlite = pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="_db_with_embeddings uses a hand-rolled :memory: SQLite schema",
)


def test_vector_blob_round_trip():
    vec = np.array([0.25, -1.5, 3.0], dtype="<f4")
    blob = vector_to_blob(vec)
    assert isinstance(blob, bytes)
    assert len(blob) == 12  # 3 × float32
    out = blob_to_vector(blob)
    assert np.allclose(out, vec)


def test_l2_normalize_unit_length_and_zero_safe():
    vec = l2_normalize(np.array([3.0, 4.0], dtype="<f4"))
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-6
    zero = l2_normalize(np.zeros(4, dtype="<f4"))
    assert float(np.linalg.norm(zero)) == 0.0


def test_embeddings_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EMBEDDINGS_ENABLED", raising=False)
    assert embeddings_enabled() is False
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "1")
    assert embeddings_enabled() is True
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    assert embeddings_enabled() is False


async def _db_with_embeddings() -> object:
    db = await get_db()
    await db.executescript(
        """
        CREATE TABLE cve_embeddings (
            cve_id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    vectors = {
        "CVE-2024-0001": [1.0, 0.0, 0.0],
        "CVE-2024-0002": [0.9, 0.1, 0.0],   # closest to 0001
        "CVE-2024-0003": [0.0, 1.0, 0.0],   # orthogonal
        "CVE-2024-0004": [-1.0, 0.0, 0.0],  # opposite
    }
    for cve_id, vec in vectors.items():
        blob = vector_to_blob(l2_normalize(np.array(vec, dtype="<f4")))
        await db.execute(
            "INSERT INTO cve_embeddings (cve_id, model, dim, vector) VALUES (?, ?, 3, ?)",
            (cve_id, MODEL, blob),
        )
    # A row from another model must never enter the scan.
    await db.execute(
        "INSERT INTO cve_embeddings (cve_id, model, dim, vector) VALUES (?, ?, 3, ?)",
        ("CVE-2024-0099", "other-model", vector_to_blob(np.array([1.0, 0.0, 0.0], dtype="<f4"))),
    )
    await db.commit()
    return db


@_requires_sqlite
def test_find_similar_numpy_orders_by_cosine_and_excludes_self(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    async def run():
        db = await _db_with_embeddings()
        results = await find_similar_cves(db, "CVE-2024-0001", limit=3)
        await db.close()
        return results

    results = run_db_test(run())
    ids = [r["cve_id"] for r in results]
    assert "CVE-2024-0001" not in ids
    assert "CVE-2024-0099" not in ids  # different model excluded
    assert ids[0] == "CVE-2024-0002"  # highest cosine similarity first
    assert ids[-1] == "CVE-2024-0004"  # opposite vector ranks last
    sims = [r["similarity"] for r in results]
    assert sims == sorted(sims, reverse=True)
    assert sims[0] > 0.9


@_requires_sqlite
def test_find_similar_returns_none_without_target_vector(monkeypatch):
    """None signals the caller to use the deterministic heuristic fallback."""
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    async def run():
        db = await _db_with_embeddings()
        result = await find_similar_cves(db, "CVE-1999-9999", limit=3)
        await db.close()
        return result

    assert run_db_test(run()) is None


class _FakeTextEmbedding:
    """Deterministic stand-in for fastembed — no ONNX download in CI."""

    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs

    def embed(self, texts):
        for text in texts:
            seed = float(len(text) % 7 + 1)
            yield np.array([seed, 1.0, 0.5], dtype="<f4")


def test_import_defaults_hf_home_before_fastembed(tmp_path):
    """HF_HOME must be present before fastembed imports huggingface_hub."""
    cache = tmp_path / "models"
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["EMBEDDINGS_CACHE_DIR"] = str(cache)
    env.pop("HF_HOME", None)
    env["PYTHONPATH"] = (
        str(backend_dir)
        if not env.get("PYTHONPATH")
        else f"{backend_dir}{os.pathsep}{env['PYTHONPATH']}"
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os\n"
                "import ml.embeddings\n"
                "expected = os.path.join(os.environ['EMBEDDINGS_CACHE_DIR'], 'hf-home')\n"
                "assert os.environ['HF_HOME'] == expected\n"
                "try:\n"
                "    from huggingface_hub import constants\n"
                "except ModuleNotFoundError:\n"
                "    pass\n"
                "else:\n"
                "    assert constants.HF_HOME == expected\n"
            ),
        ],
        check=True,
        env=env,
    )


def test_get_model_passes_writable_cache_dir(tmp_path, monkeypatch):
    """Production runs under systemd ProtectSystem=strict: the home-dir
    HuggingFace cache is read-only (EROFS). EMBEDDINGS_CACHE_DIR must reach
    fastembed as cache_dir and steer the hf-xet chunk cache via HF_HOME."""
    cache = tmp_path / "models"
    monkeypatch.setenv("EMBEDDINGS_CACHE_DIR", str(cache))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setattr(emb, "TextEmbedding", _FakeTextEmbedding)
    monkeypatch.setattr(emb, "_model", None)
    monkeypatch.setattr(emb, "_model_name", None)

    model = emb._get_model(MODEL)
    assert model.kwargs.get("cache_dir") == str(cache)
    assert cache.is_dir()  # created if missing
    assert os.environ["HF_HOME"] == str(cache / "hf-home")


def test_get_model_default_has_no_cache_kwargs(monkeypatch):
    monkeypatch.delenv("EMBEDDINGS_CACHE_DIR", raising=False)
    monkeypatch.setattr(emb, "TextEmbedding", _FakeTextEmbedding)
    monkeypatch.setattr(emb, "_model", None)
    monkeypatch.setattr(emb, "_model_name", None)

    model = emb._get_model(MODEL)
    assert "cache_dir" not in model.kwargs


@pytest.mark.skipif(is_postgres(), reason="fake 3-dim vectors are incompatible with pgvector(384)")
def test_backfill_embeds_missing_cves_with_fake_model(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "emb.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)
    monkeypatch.setattr(emb, "TextEmbedding", _FakeTextEmbedding)
    monkeypatch.setattr(emb, "_model", None)
    monkeypatch.setattr(emb, "_model_name", None)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-1111", "SQL injection in example app.", date.today().isoformat()),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-2222", "", date.today().isoformat()),  # no description → skipped
            )
            await db.commit()
            stats = await run_embeddings_backfill(db)
            rows = await db.execute_fetchall(
                "SELECT cve_id, model, dim, vector FROM cve_embeddings"
            )
            # Second pass is a no-op (idempotent).
            stats2 = await run_embeddings_backfill(db)
            return stats, stats2, [dict(r) for r in rows]
        finally:
            await db.close()

    stats, stats2, rows = run_db_test(run())
    assert stats["embedded"] == 1
    assert stats2["embedded"] == 0
    assert len(rows) == 1
    assert rows[0]["cve_id"] == "CVE-2024-1111"
    assert rows[0]["model"] == MODEL
    assert rows[0]["dim"] == 3
    vec = blob_to_vector(rows[0]["vector"])
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-5  # stored normalized


def test_embeddings_auto_on_ingest_requires_both_flags(monkeypatch):
    from ml import embeddings as emb

    monkeypatch.setenv("EMBEDDINGS_ENABLED", "1")
    monkeypatch.setenv("EMBEDDINGS_AUTO_ON_INGEST", "0")
    assert emb.embeddings_auto_on_ingest_enabled() is False
    monkeypatch.setenv("EMBEDDINGS_AUTO_ON_INGEST", "1")
    assert emb.embeddings_auto_on_ingest_enabled() is True
    monkeypatch.delenv("EMBEDDINGS_AUTO_ON_INGEST", raising=False)
    assert emb.embeddings_auto_on_ingest_enabled() is True  # default on


def test_backfill_skips_gracefully_when_fastembed_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "nofe.db"))
    monkeypatch.setattr(emb, "TextEmbedding", None)
    monkeypatch.setattr(emb, "_missing_dep_logged", False)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-3333", "Some bug.", date.today().isoformat()),
            )
            await db.commit()
            return await run_embeddings_backfill(db)
        finally:
            await db.close()

    stats = run_db_test(run())
    assert stats["embedded"] == 0
    assert stats.get("skipped") == "fastembed missing"


def _seed_related_db(db_path: str) -> None:
    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            rows = [
                ("CVE-2024-0001", "TensorFlow RCE.", 9.8, "CRITICAL", json.dumps(["google:tensorflow"])),
                ("CVE-2024-0002", "TensorFlow DoS.", 6.5, "MEDIUM", json.dumps(["google:tensorflow"])),
                ("CVE-2024-0003", "Semantically similar issue.", 8.0, "HIGH", "[]"),
            ]
            for cve_id, desc, cvss, sev, products in rows:
                await db.execute(
                    """
                    INSERT INTO cves (cve_id, description, cvss_score, severity,
                                      published, affected_products)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cve_id, desc, cvss, sev, today, products),
                )
            # Vectors: 0001↔0003 nearly identical, 0002 distant.
            vectors = {
                "CVE-2024-0001": [1.0, 0.0],
                "CVE-2024-0003": [0.99, 0.01],
                "CVE-2024-0002": [0.0, 1.0],
            }
            for cve_id, vec in vectors.items():
                await db.execute(
                    "INSERT INTO cve_embeddings (cve_id, model, dim, vector) VALUES (?, ?, 2, ?)",
                    (cve_id, MODEL, vector_to_blob(l2_normalize(np.array(vec, dtype="<f4")))),
                )
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())


@pytest.fixture
def related_client(tmp_path, monkeypatch):
    db_path = tmp_path / "related.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    _seed_related_db(str(db_path))

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        yield client


@pytest.mark.skipif(is_postgres(), reason="fake 2-dim vectors are incompatible with pgvector(384)")
def test_related_endpoint_heuristic_when_embeddings_disabled(related_client, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    body = related_client.get("/api/cves/CVE-2024-0001/related").json()
    assert body["meta"]["method"] == "product_heuristic"
    ids = [c["cve_id"] for c in body["data"]]
    assert ids == ["CVE-2024-0002"]  # shared google:tensorflow product
    assert all("similarity" not in c for c in body["data"])


@pytest.mark.skipif(is_postgres(), reason="fake 2-dim vectors are incompatible with pgvector(384)")
def test_related_endpoint_semantic_when_embeddings_enabled(related_client, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "1")
    body = related_client.get("/api/cves/CVE-2024-0001/related?limit=2").json()
    assert body["meta"]["method"] == "embeddings"
    ids = [c["cve_id"] for c in body["data"]]
    assert ids[0] == "CVE-2024-0003"  # nearest vector, no shared product needed
    for item in body["data"]:
        assert "similarity" in item
        # Existing card fields preserved (additive response shape).
        for field in ("cve_id", "description", "cvss_score", "severity", "published", "epss_score"):
            assert field in item


@pytest.mark.skipif(is_postgres(), reason="fake 2-dim vectors are incompatible with pgvector(384)")
def test_related_endpoint_falls_back_when_target_has_no_vector(tmp_path, monkeypatch):
    """Embeddings enabled but this CVE not yet embedded → heuristic fallback.

    Self-contained (not `related_client`): the vector deletion below must run
    before the TestClient opens its own pool — a bare run_db_test() call
    against an already-open fixture pool would bind to a different event
    loop (Postgres), the same issue fixed in test_auth_setup.py."""
    db_path = tmp_path / "related-no-vector.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "1")

    _seed_related_db(str(db_path))

    async def run():
        db = await database.get_db()
        try:
            await db.execute(
                "DELETE FROM cve_embeddings WHERE cve_id = 'CVE-2024-0001'"
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(run())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        body = client.get("/api/cves/CVE-2024-0001/related").json()
    assert body["meta"]["method"] == "product_heuristic"
    assert [c["cve_id"] for c in body["data"]] == ["CVE-2024-0002"]


def test_scheduler_embeddings_job_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")
    from scheduler import run_embeddings_sync

    assert run_db_test(run_embeddings_sync()) is False
