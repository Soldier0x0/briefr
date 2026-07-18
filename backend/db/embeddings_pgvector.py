"""pgvector helpers for embeddings E1 (BLOB ↔ vector(384) literal).

Used by Alembic 032 data migration and Postgres-only tests. Runtime read/write
of the `embeddings` table lands in E2 — this module stays schema/migrate-only.
"""

from __future__ import annotations

import hashlib
import struct
from datetime import datetime, timezone
from typing import Any

DEFAULT_EMBEDDING_DIMS = 384
DEFAULT_EMBEDDINGS_MODEL = "BAAI/bge-small-en-v1.5"


def blob_to_pgvector_literal(
    blob: bytes | memoryview | None, *, expected_dim: int = DEFAULT_EMBEDDING_DIMS
) -> str | None:
    """Decode float32 little-endian BLOB to a pgvector text literal, or None if invalid."""
    if blob is None:
        return None
    raw = bytes(blob)
    if len(raw) != expected_dim * 4:
        return None
    floats = struct.unpack(f"<{expected_dim}f", raw)
    return "[" + ",".join(repr(float(f)) for f in floats) + "]"


def migrated_content_hash(blob: bytes) -> str:
    """Placeholder content_hash for BLOB-migrated rows (E2 recomputes from rich text)."""
    return "migrated:" + hashlib.sha256(blob).hexdigest()[:32]


def parse_embedding_updated_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value.strip():
        text_val = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text_val)
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)
