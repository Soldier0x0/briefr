"""pgvector / embeddings helpers (E1 migrate + E2 write path).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from typing import Any

DEFAULT_EMBEDDING_DIMS = 384
DEFAULT_EMBEDDINGS_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_TEXT_MAX_CHARS = 2000
ENTITY_TYPE_CVE = "cve"


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


def is_placeholder_content_hash(content_hash: str | None) -> bool:
    return bool(content_hash) and str(content_hash).startswith("migrated:")


def _join_json_list(raw: Any) -> str:
    """Normalize JSON-array or comma/newline text into a single spaced string."""
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return " ".join(parts)
    text = str(raw).strip()
    if not text or text in ("[]", "null", "None"):
        return ""
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
        if isinstance(parsed, list):
            parts = [str(x).strip() for x in parsed if str(x).strip()]
            return " ".join(parts)
    return text


def build_cve_embed_text(
    *,
    description: str | None,
    summary: str | None = None,
    affected_products: Any = None,
    cwe_ids: Any = None,
    max_chars: int = EMBED_TEXT_MAX_CHARS,
) -> str:
    """Deterministic rich CVE text for embedding (design §5.2)."""
    parts: list[str] = []
    desc = (description or "").strip()
    if desc:
        parts.append(desc)
    summ = (summary or "").strip()
    if summ:
        parts.append(summ)
    products = _join_json_list(affected_products)
    if products:
        parts.append(products)
    cwes = _join_json_list(cwe_ids)
    if cwes:
        parts.append(cwes)
    text = "\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def content_hash_for_embed_text(text: str, model: str) -> str:
    """sha256(normalized_text + '\\n' + model) — model change invalidates naturally."""
    normalized = (text or "").strip()
    payload = f"{normalized}\n{model}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
