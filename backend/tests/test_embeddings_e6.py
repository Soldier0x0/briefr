"""Embeddings E6 — MITRE technique embeddings + typed search hits."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db
from db.embeddings_pgvector import (
    ENTITY_TYPE_TECHNIQUE,
    build_technique_embed_text,
    content_hash_for_embed_text,
)
from db.embeddings_store import (
    get_techniques_needing_embeddings,
    upsert_technique_embedding_row,
)
from ml.embeddings import l2_normalize, vector_to_blob
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


def test_build_technique_embed_text():
    text = build_technique_embed_text(
        name="Spearphishing Attachment",
        description="Adversaries send phishing with attachments.",
        tactic="initial-access",
    )
    assert "Spearphishing" in text
    assert "initial-access" in text
    h = content_hash_for_embed_text(text, MODEL)
    assert len(h) == 64


def test_technique_pending_and_upsert(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e6.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO mitre_techniques (technique_id, name, description, tactic, url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "T1566.001",
                    "Spearphishing Attachment",
                    "Phishing with malicious attachment.",
                    "initial-access",
                    "https://attack.mitre.org/techniques/T1566/001/",
                ),
            )
            await db.commit()
            pending = await get_techniques_needing_embeddings(db, MODEL, limit=10)
            assert any(p["technique_id"] == "T1566.001" for p in pending)
            item = next(p for p in pending if p["technique_id"] == "T1566.001")
            blob = vector_to_blob(l2_normalize(np.array([1.0, 0.0, 0.0], dtype="<f4")))
            await upsert_technique_embedding_row(
                db, "T1566.001", MODEL, 3, blob, item["content_hash"]
            )
            await db.commit()
            pending2 = await get_techniques_needing_embeddings(db, MODEL, limit=10)
            assert not any(p["technique_id"] == "T1566.001" for p in pending2)
            rows = await db.execute_fetchall(
                "SELECT entity_type, entity_id FROM embeddings WHERE entity_id = ?",
                ("T1566.001",),
            )
            assert rows[0]["entity_type"] == ENTITY_TYPE_TECHNIQUE
            return True
        finally:
            await db.close()

    assert run_db_test(run()) is True
