"""Embeddings E2 — rich-text dual-write + content_hash."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
import ml.embeddings as emb
from database import init_db
from db.embeddings_pgvector import (
    build_cve_embed_text,
    content_hash_for_embed_text,
    is_placeholder_content_hash,
    migrated_content_hash,
)
from ml.embeddings import (
    blob_to_vector,
    l2_normalize,
    run_embeddings_backfill,
    vector_to_blob,
)
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


class _FakeTextEmbedding:
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs

    def embed(self, texts):
        for text in texts:
            seed = float(len(text) % 7 + 1)
            yield np.array([seed, 1.0, 0.5], dtype="<f4")


def test_build_cve_embed_text_rich_and_hash():
    text = build_cve_embed_text(
        description="SQL injection",
        summary="Short summary",
        affected_products='["acme:widget"]',
        cwe_ids='["CWE-89"]',
    )
    assert "SQL injection" in text
    assert "Short summary" in text
    assert "acme:widget" in text
    assert "CWE-89" in text
    h1 = content_hash_for_embed_text(text, MODEL)
    h2 = content_hash_for_embed_text(text, MODEL)
    assert h1 == h2
    assert len(h1) == 64
    assert content_hash_for_embed_text(text, "other-model") != h1
    assert is_placeholder_content_hash(migrated_content_hash(b"abc"))
    assert not is_placeholder_content_hash(h1)


def test_backfill_dual_writes_embeddings_table(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite dual-write path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e2.db"))
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
                INSERT INTO cves (
                    cve_id, description, summary, affected_products, cwe_ids, published
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2024-E2A",
                    "Buffer overflow in parser.",
                    "Critical remote crash",
                    '["vendor:product"]',
                    '["CWE-120"]',
                    date.today().isoformat(),
                ),
            )
            await db.commit()
            stats = await run_embeddings_backfill(db)
            legacy = await db.execute_fetchall(
                "SELECT cve_id FROM cve_embeddings WHERE cve_id = ?",
                ("CVE-2024-E2A",),
            )
            rows = await db.execute_fetchall(
                """
                SELECT entity_id, model, dims, content_hash, length(embedding) AS nbytes
                FROM embeddings
                WHERE entity_type = 'cve' AND entity_id = ?
                """,
                ("CVE-2024-E2A",),
            )
            stats2 = await run_embeddings_backfill(db)
            return stats, stats2, legacy, [dict(r) for r in rows]
        finally:
            await db.close()

    stats, stats2, legacy, rows = run_db_test(run())
    assert stats["embedded"] == 1
    assert stats.get("pgvector_writes") is True
    assert stats2["embedded"] == 0
    assert legacy
    assert len(rows) == 1
    assert rows[0]["model"] == MODEL
    assert rows[0]["dims"] == 3
    assert not is_placeholder_content_hash(rows[0]["content_hash"])
    assert rows[0]["nbytes"] == 12


def test_backfill_reembeds_migrated_placeholder(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e2m.db"))
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
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-E2M", "Needs re-embed after E1 migrate.", date.today().isoformat()),
            )
            blob = vector_to_blob(l2_normalize(np.array([1.0, 0.0, 0.0], dtype="<f4")))
            await db.execute(
                """
                INSERT INTO embeddings (
                    entity_type, entity_id, model, dims, embedding, content_hash, updated_at
                ) VALUES ('cve', ?, ?, 3, ?, ?, datetime('now'))
                """,
                ("CVE-2024-E2M", MODEL, blob, migrated_content_hash(blob)),
            )
            await db.commit()
            before = await db.execute_fetchall(
                "SELECT content_hash FROM embeddings WHERE entity_id = ?",
                ("CVE-2024-E2M",),
            )
            stats = await run_embeddings_backfill(db)
            after = await db.execute_fetchall(
                "SELECT content_hash FROM embeddings WHERE entity_id = ?",
                ("CVE-2024-E2M",),
            )
            return stats, before[0]["content_hash"], after[0]["content_hash"]
        finally:
            await db.close()

    stats, before, after = run_db_test(run())
    assert stats["embedded"] == 1
    assert is_placeholder_content_hash(before)
    assert not is_placeholder_content_hash(after)


def test_pgvector_writes_can_be_disabled(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e2off.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)
    monkeypatch.setenv("EMBEDDINGS_PGVECTOR", "0")
    monkeypatch.setattr(emb, "TextEmbedding", _FakeTextEmbedding)
    monkeypatch.setattr(emb, "_model", None)
    monkeypatch.setattr(emb, "_model_name", None)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-E2OFF", "Legacy only.", date.today().isoformat()),
            )
            await db.commit()
            stats = await run_embeddings_backfill(db)
            emb_rows = await db.execute_fetchall("SELECT entity_id FROM embeddings")
            legacy = await db.execute_fetchall("SELECT cve_id FROM cve_embeddings")
            return stats, emb_rows, legacy
        finally:
            await db.close()

    stats, emb_rows, legacy = run_db_test(run())
    assert stats["embedded"] == 1
    assert stats.get("pgvector_writes") is False
    assert not emb_rows
    assert legacy
