"""Embeddings E1 — pgvector foundation (extension, table, BLOB migrate)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.embeddings_pgvector import (
    DEFAULT_EMBEDDING_DIMS,
    DEFAULT_EMBEDDINGS_MODEL,
    blob_to_pgvector_literal,
    migrated_content_hash,
)
from ml.embeddings import l2_normalize, vector_to_blob
from tests.conftest import run_db_test

pytestmark_pg = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)

_VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_032_revision_file_and_chain():
    path = _VERSIONS_DIR / "032_embeddings_pgvector.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision = "032_embeddings_pgvector"' in source
    assert 'down_revision = "031_stack_backfill"' in source
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert "vector(384)" in source
    assert "hnsw" in source.lower()
    # Gemini: dims/model frozen in migration; inserts batched
    assert "_MIGRATION_EMBEDDING_DIMS = 384" in source
    assert "_MIGRATE_BATCH_SIZE" in source
    assert "from db.embeddings_pgvector import" in source
    assert "DEFAULT_EMBEDDING_DIMS," not in source
    assert "DEFAULT_EMBEDDINGS_MODEL," not in source


def test_blob_to_pgvector_literal_round_trip_shape():
    vec = l2_normalize(np.arange(DEFAULT_EMBEDDING_DIMS, dtype="<f4"))
    blob = vector_to_blob(vec)
    literal = blob_to_pgvector_literal(blob)
    assert literal is not None
    assert literal.startswith("[") and literal.endswith("]")
    parts = literal[1:-1].split(",")
    assert len(parts) == DEFAULT_EMBEDDING_DIMS
    assert blob_to_pgvector_literal(b"\x00\x01") is None
    assert migrated_content_hash(blob).startswith("migrated:")


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_pgvector_extension_and_embeddings_table():
    async def run():
        from database import get_db

        db = await get_db()
        ext = await db.execute_fetchall(
            "SELECT 1 AS ok FROM pg_extension WHERE extname = 'vector'"
        )
        assert ext, "vector extension missing — use pgvector/pgvector:pg16 image"

        cols = await db.execute_fetchall(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'intel' AND table_name = 'embeddings'
            ORDER BY ordinal_position
            """
        )
        by_name = {r["column_name"]: r for r in cols}
        assert "embedding" in by_name
        assert by_name["embedding"]["udt_name"] == "vector"

        vec = l2_normalize(np.ones(DEFAULT_EMBEDDING_DIMS, dtype="<f4"))
        literal = blob_to_pgvector_literal(vector_to_blob(vec))
        assert literal is not None
        await db.execute(
            """
            INSERT INTO intel.embeddings (
                entity_type, entity_id, model, dims, embedding, content_hash
            )
            VALUES ('cve', 'CVE-2099-E1TEST', $1, $2, CAST($3 AS vector), $4)
            ON CONFLICT (entity_type, entity_id, model) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                content_hash = EXCLUDED.content_hash,
                updated_at = NOW()
            """,
            (
                DEFAULT_EMBEDDINGS_MODEL,
                DEFAULT_EMBEDDING_DIMS,
                literal,
                "test:e1",
            ),
        )
        hits = await db.execute_fetchall(
            """
            SELECT entity_id,
                   embedding <=> CAST($1 AS vector) AS dist
            FROM intel.embeddings
            WHERE entity_type = 'cve' AND entity_id = 'CVE-2099-E1TEST'
            """,
            (literal,),
        )
        assert hits
        assert float(hits[0]["dist"]) < 1e-5

    run_db_test(run())


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_cve_embeddings_blob_migrate_helper():
    """Re-run BLOB→vector insert for one row (same path as Alembic 032)."""

    async def run():
        from database import get_db

        rng = np.random.default_rng(42)
        vec = l2_normalize(rng.standard_normal(DEFAULT_EMBEDDING_DIMS).astype("<f4"))
        blob = vector_to_blob(vec)
        cve_id = "CVE-2099-E1BLOB"
        model = DEFAULT_EMBEDDINGS_MODEL

        db = await get_db()
        await db.execute(
            """
            INSERT INTO cve_embeddings (cve_id, model, dim, vector, updated_at)
            VALUES ($1, $2, $3, $4, NOW()::text)
            ON CONFLICT (cve_id) DO UPDATE SET
                model = EXCLUDED.model,
                dim = EXCLUDED.dim,
                vector = EXCLUDED.vector
            """,
            (cve_id, model, DEFAULT_EMBEDDING_DIMS, blob),
        )
        await db.execute(
            "DELETE FROM embeddings WHERE entity_type = 'cve' AND entity_id = $1 AND model = $2",
            (cve_id, model),
        )
        literal = blob_to_pgvector_literal(blob)
        assert literal is not None
        await db.execute(
            """
            INSERT INTO embeddings (
                entity_type, entity_id, model, dims, embedding, content_hash, updated_at
            )
            VALUES (
                'cve', $1, $2, $3, CAST($4 AS vector), $5, NOW()
            )
            """,
            (
                cve_id,
                model,
                DEFAULT_EMBEDDING_DIMS,
                literal,
                migrated_content_hash(blob),
            ),
        )
        rows = await db.execute_fetchall(
            """
            SELECT dims, content_hash,
                   embedding <=> CAST($1 AS vector) AS dist
            FROM embeddings
            WHERE entity_type = 'cve' AND entity_id = $2 AND model = $3
            """,
            (literal, cve_id, model),
        )
        assert len(rows) == 1
        assert int(rows[0]["dims"]) == DEFAULT_EMBEDDING_DIMS
        assert str(rows[0]["content_hash"]).startswith("migrated:")
        assert float(rows[0]["dist"]) < 1e-5

    run_db_test(run())
