"""CVE description embeddings — env-gated, CPU-only, scheduler-side (V1.3 / E2).

**E2 write path:** vectors are dual-written to:
- ``embeddings`` (pgvector ``vector(384)`` on Postgres; BLOB on SQLite) with
  rich CVE text + ``content_hash``
- legacy ``cve_embeddings`` BLOBs (one-release read-fallback for related until E3)

Similarity on the request path still scans legacy BLOBs with NumPy until E3.
Model inference (fastembed/ONNX) runs only inside the scheduler backfill job.

Disabled by default (``EMBEDDINGS_ENABLED=0``). Set ``EMBEDDINGS_PGVECTOR=0``
to skip writes to the ``embeddings`` table (legacy-only).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import asyncio
import logging
import os

def _default_hf_home_for_cache(cache_dir: str) -> None:
    # huggingface_hub freezes HF_HOME-derived constants at import time; fastembed
    # imports it underneath, so default HF_HOME before importing fastembed.
    os.environ.setdefault("HF_HOME", os.path.join(cache_dir, "hf-home"))


_embeddings_cache_dir = os.environ.get("EMBEDDINGS_CACHE_DIR", "").strip()
if _embeddings_cache_dir:
    _default_hf_home_for_cache(_embeddings_cache_dir)

import numpy as np

from database import (
    get_all_cve_embeddings,
    get_cve_embedding,
    upsert_cve_embedding,
)
from db.embeddings_store import (
    embeddings_pgvector_writes_enabled,
    get_cves_needing_embeddings,
    get_cves_needing_embeddings_by_ids,
    upsert_cve_embedding_row,
)

try:  # optional local model — only needed when EMBEDDINGS_ENABLED=1
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover — exercised on minimal installs
    TextEmbedding = None

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDINGS_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_BATCH_SIZE = 64
# Re-export for callers/tests that imported the constant from this module.
EMBED_TEXT_MAX_CHARS = 2000

# Lazy singleton — loading the ONNX weights costs ~100 MB RSS, so the model
# is instantiated only when the scheduler backfill actually runs.
_model: "TextEmbedding | None" = None
_model_name: str | None = None
_missing_dep_logged = False


def embeddings_enabled() -> bool:
    return os.environ.get("EMBEDDINGS_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def embeddings_auto_on_ingest_enabled() -> bool:
    return embeddings_enabled() and os.environ.get(
        "EMBEDDINGS_AUTO_ON_INGEST", "0"
    ).strip().lower() in ("1", "true", "yes")


def get_embeddings_ingest_max_per_run() -> int:
    return int(os.environ.get("EMBEDDINGS_INGEST_MAX_PER_RUN", "25"))


def get_embeddings_model_name() -> str:
    return (
        os.environ.get("EMBEDDINGS_MODEL", DEFAULT_EMBEDDINGS_MODEL).strip()
        or DEFAULT_EMBEDDINGS_MODEL
    )


def get_embeddings_max_per_run() -> int:
    return int(os.environ.get("EMBEDDINGS_MAX_PER_RUN", "2000"))


def get_embeddings_cache_dir() -> str:
    """Model download/cache directory. Must be writable by the service user —
    production runs under systemd ProtectSystem=strict, where the home-dir
    HuggingFace cache is read-only (deploy unit sets this to
    /var/lib/briefr/models). Empty = fastembed's default (fine for dev)."""
    return os.environ.get("EMBEDDINGS_CACHE_DIR", "").strip()


def vector_to_blob(vector) -> bytes:
    """float32 little-endian bytes."""
    return np.asarray(vector, dtype="<f4").tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype="<f4")
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr
    return arr / norm


def _get_model(model_name: str):
    global _model, _model_name
    if TextEmbedding is None:
        raise RuntimeError(
            "EMBEDDINGS_ENABLED=1 but the 'fastembed' package is not installed "
            "— run: pip install fastembed"
        )
    if _model is None or _model_name != model_name:
        cache_dir = get_embeddings_cache_dir()
        logger.info(
            "Loading embeddings model %s (CPU, ONNX%s)",
            model_name,
            f", cache={cache_dir}" if cache_dir else "",
        )
        kwargs = {}
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            kwargs["cache_dir"] = cache_dir
            _default_hf_home_for_cache(cache_dir)
        _model = TextEmbedding(model_name=model_name, **kwargs)
        _model_name = model_name
    return _model


def _embed_texts(model, texts: list[str]) -> list[np.ndarray]:
    """Blocking model inference — call via asyncio.to_thread only."""
    return [np.asarray(vec, dtype="<f4") for vec in model.embed(texts)]


async def run_embeddings_backfill(
    db,
    progress_cb=None,
    *,
    cve_id_filter: set[str] | None = None,
) -> dict:
    """Embed CVE rich-text that is missing / migrated: / hash-mismatched.

    Scheduler-side only. Batched + committed per batch so an interrupted run
    resumes where it left off; capped per run by EMBEDDINGS_MAX_PER_RUN (or
    EMBEDDINGS_INGEST_MAX_PER_RUN when ``cve_id_filter`` is set).
    """
    global _missing_dep_logged

    model_name = get_embeddings_model_name()
    cap = (
        get_embeddings_ingest_max_per_run()
        if cve_id_filter
        else get_embeddings_max_per_run()
    )
    if cve_id_filter:
        pending = await get_cves_needing_embeddings_by_ids(
            db, model_name, cve_id_filter
        )
        pending = pending[:cap]
    else:
        pending = await get_cves_needing_embeddings(db, model_name, limit=cap * 4)
        pending = pending[:cap]
    if not pending:
        return {"embedded": 0, "model": model_name}

    if TextEmbedding is None:
        if not _missing_dep_logged:
            logger.warning(
                "EMBEDDINGS_ENABLED=1 but 'fastembed' is not installed — "
                "embeddings backfill skipped (pip install fastembed)"
            )
            _missing_dep_logged = True
        return {"embedded": 0, "model": model_name, "skipped": "fastembed missing"}

    model = _get_model(model_name)
    write_pgvector = embeddings_pgvector_writes_enabled()
    embedded = 0
    total = len(pending)
    total_batches = (total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for batch_num, offset in enumerate(range(0, total, EMBED_BATCH_SIZE), start=1):
        batch = pending[offset : offset + EMBED_BATCH_SIZE]
        if progress_cb:
            progress_cb(
                f"Embedding CVE descriptions with {model_name}: "
                f"batch {batch_num}/{total_batches} "
                f"({min(offset + EMBED_BATCH_SIZE, total)}/{total} CVEs)…"
            )
        texts = [item["embed_text"] for item in batch]
        vectors = await asyncio.to_thread(_embed_texts, model, texts)
        for item, vector in zip(batch, vectors):
            normalized = l2_normalize(vector)
            blob = vector_to_blob(normalized)
            dims = int(normalized.size)
            await upsert_cve_embedding(
                db,
                item["cve_id"],
                model_name,
                dims,
                blob,
            )
            if write_pgvector:
                await upsert_cve_embedding_row(
                    db,
                    item["cve_id"],
                    model_name,
                    dims,
                    blob,
                    item["content_hash"],
                )
        await db.commit()
        embedded += len(batch)

    return {
        "embedded": embedded,
        "model": model_name,
        "pgvector_writes": write_pgvector,
    }


async def find_similar_cves(db, cve_id: str, limit: int = 5) -> list[dict] | None:
    """Top-k semantically similar CVEs by cosine similarity.

    Returns None when the target CVE has no stored vector — the caller must
    fall back to the deterministic shared-product heuristic. No model
    inference happens here: this is a pure scan over stored BLOBs.
    """
    model_name = get_embeddings_model_name()
    target_blob = await get_cve_embedding(db, cve_id, model_name)
    if target_blob is None:
        return None

    target = blob_to_vector(target_blob)
    rows = await get_all_cve_embeddings(db, model_name, exclude_cve_id=cve_id)
    rows = [(rid, blob) for rid, blob in rows if len(blob) == target.nbytes]
    if not rows:
        return []

    ids = [rid for rid, _blob in rows]
    matrix = np.frombuffer(b"".join(blob for _rid, blob in rows), dtype="<f4")
    matrix = matrix.reshape(len(rows), target.size)
    # Vectors are L2-normalized at write time, so cosine == dot product.
    similarities = matrix @ target

    k = min(limit, len(ids))
    top = np.argpartition(-similarities, k - 1)[:k]
    top = top[np.argsort(-similarities[top])]
    return [
        {"cve_id": ids[i], "similarity": round(float(similarities[i]), 4)}
        for i in top
    ]
