"""E7 — CVE embedding freshness on content_hash drift."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
import ml.embeddings as emb
from database import init_db
from db.embeddings_pgvector import content_hash_for_embed_text
from db.embeddings_store import get_cves_needing_embeddings, upsert_cve_embedding_row
from ml.embeddings import vector_to_blob
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


class _FakeTextEmbedding:
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name

    def embed(self, texts):
        for text in texts:
            seed = float(len(text) % 7 + 1)
            yield np.array([seed, 1.0, 0.5], dtype="<f4")


def test_pending_includes_hash_drift_after_description_change(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite freshness path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e7-fresh.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)
    monkeypatch.setenv("EMBEDDINGS_PGVECTOR", "1")
    monkeypatch.setattr(emb, "TextEmbedding", _FakeTextEmbedding)
    monkeypatch.setattr(emb, "_model", None)
    monkeypatch.setattr(emb, "_model_name", None)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, summary, published, severity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2026-E7-001",
                    "Original nginx buffer overflow",
                    "orig",
                    "2026-01-01",
                    "HIGH",
                ),
            )
            blob = vector_to_blob(np.array([1.0, 0.0, 0.0], dtype="<f4"))
            from db.embeddings_pgvector import build_cve_embed_text

            text = build_cve_embed_text(
                description="Original nginx buffer overflow",
                summary="orig",
                affected_products=None,
                cwe_ids=None,
            )
            text_hash = content_hash_for_embed_text(text, MODEL)
            await upsert_cve_embedding_row(
                db,
                "CVE-2026-E7-001",
                MODEL,
                3,
                blob,
                text_hash,
            )
            pending = await get_cves_needing_embeddings(db, MODEL, limit=20)
            assert not any(p["cve_id"] == "CVE-2026-E7-001" for p in pending)

            await db.execute(
                "UPDATE cves SET description = ? WHERE cve_id = ?",
                ("Updated nginx RCE with auth bypass", "CVE-2026-E7-001"),
            )
            pending2 = await get_cves_needing_embeddings(db, MODEL, limit=20)
            assert any(p["cve_id"] == "CVE-2026-E7-001" for p in pending2)
        finally:
            await db.close()

    run_db_test(run())
