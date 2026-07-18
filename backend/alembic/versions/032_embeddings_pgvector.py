"""pgvector extension + embeddings table; migrate cve_embeddings BLOBs (E1).

Revision ID: 032_embeddings_pgvector
Revises: 031_stack_backfill
Create Date: 2026-07-18

Requires a pgvector-capable Postgres image (local/CI: pgvector/pgvector:pg16;
production cutover: pgvector/pgvector:pg17 — see docs/POSTGRES.md).
Legacy cve_embeddings is left in place for one release (read-fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import op
from sqlalchemy import text

# Alembic runs with cwd/backend on path inconsistently — ensure backend/ import root.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from db.embeddings_pgvector import (  # noqa: E402
    blob_to_pgvector_literal,
    migrated_content_hash,
    parse_embedding_updated_at,
)

# Frozen at migration write-time — do not import app defaults (Gemini: if
# EMBEDDINGS_MODEL / dims change later, replaying this revision must still
# match vector(384) and migrate legacy 384-d BLOBs).
_MIGRATION_EMBEDDING_DIMS = 384
_MIGRATION_EMBEDDINGS_MODEL = "BAAI/bge-small-en-v1.5"
_MIGRATE_BATCH_SIZE = 1000

revision = "032_embeddings_pgvector"
down_revision = "031_stack_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            model TEXT NOT NULL,
            dims INT NOT NULL,
            embedding vector(384) NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (entity_type, entity_id, model)
        )
        """
    )
    # ANN index for the active CVE model (HNSW cosine). Empty-table safe.
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_embeddings_cve_hnsw
        ON embeddings USING hnsw (embedding vector_cosine_ops)
        WHERE entity_type = 'cve' AND model = '{_MIGRATION_EMBEDDINGS_MODEL}'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_embeddings_entity "
        "ON embeddings (entity_type, entity_id)"
    )
    _migrate_cve_embeddings_blobs()


def _migrate_cve_embeddings_blobs() -> None:
    """Copy float32 little-endian BLOBs into embeddings.vector(384).

    Rows with dim != 384 or corrupt byte length are skipped (E2 re-embeds).
    content_hash is a migrated: placeholder — E2 recomputes from rich CVE text.
    Inserts are chunked (Gemini) to avoid per-row round-trips on large corpora.
    """
    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT cve_id, model, dim, vector, updated_at "
            "FROM cve_embeddings"
        )
    ).mappings().all()

    insert_sql = text(
        """
        INSERT INTO embeddings (
            entity_type, entity_id, model, dims, embedding, content_hash, updated_at
        )
        VALUES (
            'cve', :entity_id, :model, :dims,
            CAST(:embedding AS vector), :content_hash, :updated_at
        )
        ON CONFLICT (entity_type, entity_id, model) DO NOTHING
        """
    )

    params: list[dict] = []
    for row in rows:
        dim = int(row["dim"] or 0)
        if dim != _MIGRATION_EMBEDDING_DIMS:
            continue
        raw = row["vector"]
        if raw is None:
            continue
        blob = bytes(raw)
        vec_literal = blob_to_pgvector_literal(blob, expected_dim=dim)
        if vec_literal is None:
            continue
        params.append(
            {
                "entity_id": str(row["cve_id"]).upper(),
                "model": str(row["model"]),
                "dims": dim,
                "embedding": vec_literal,
                "content_hash": migrated_content_hash(blob),
                "updated_at": parse_embedding_updated_at(row.get("updated_at")),
            }
        )

    for i in range(0, len(params), _MIGRATE_BATCH_SIZE):
        chunk = params[i : i + _MIGRATE_BATCH_SIZE]
        if chunk:
            conn.execute(insert_sql, chunk)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_entity")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_cve_hnsw")
    op.execute("DROP TABLE IF EXISTS embeddings")
    # Extension left installed — other objects may depend on it; safe no-op leave.
