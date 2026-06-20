"""CVE description embeddings — env-gated, CPU-only, scheduler-side (V1.3).

Vectors are stored as float32 little-endian BLOBs in SQLite
(``cve_embeddings`` table). The default similarity path is exact brute-force
cosine with NumPy — adequate at BRIEFR scale (tens of thousands of embedded
rows). ``sqlite-vec`` is an optional accelerator used only when it is
importable AND the Python build supports loadable extensions; it is never a
hard dependency and the NumPy path produces identical rankings.

Disabled by default (``EMBEDDINGS_ENABLED=0``): the tool stays fully
functional without it — ``GET /api/cves/{id}/related`` falls back to the
shared-product heuristic. Model inference (fastembed/ONNX) runs only inside
the scheduler backfill job, never on the request path; request-time
similarity is a pure lookup over vectors already in the DB.

Copyright © 2026 Sai Harsha Vardhan. All rights reserved.
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

import aiosqlite
import numpy as np

from database import (
    get_all_cve_embeddings,
    get_cve_embedding,
    get_cves_missing_embeddings,
    upsert_cve_embedding,
)

try:  # optional local model — only needed when EMBEDDINGS_ENABLED=1
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover — exercised on minimal installs
    TextEmbedding = None

try:  # optional accelerator ONLY — NumPy brute force is the default path
    import sqlite_vec
except ImportError:
    sqlite_vec = None

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDINGS_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_BATCH_SIZE = 64
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
    """float32 little-endian bytes — also the layout sqlite-vec expects."""
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


async def run_embeddings_backfill(db: aiosqlite.Connection) -> dict:
    """Embed CVE descriptions that have no vector for the active model.

    Scheduler-side only. Batched + committed per batch so an interrupted run
    resumes where it left off; capped per run by EMBEDDINGS_MAX_PER_RUN.
    """
    global _missing_dep_logged

    model_name = get_embeddings_model_name()
    pending = await get_cves_missing_embeddings(
        db, model_name, limit=get_embeddings_max_per_run()
    )
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
    embedded = 0
    for offset in range(0, len(pending), EMBED_BATCH_SIZE):
        batch = pending[offset : offset + EMBED_BATCH_SIZE]
        texts = [(item["description"] or "")[:EMBED_TEXT_MAX_CHARS] for item in batch]
        vectors = await asyncio.to_thread(_embed_texts, model, texts)
        for item, vector in zip(batch, vectors):
            normalized = l2_normalize(vector)
            await upsert_cve_embedding(
                db,
                item["cve_id"],
                model_name,
                int(normalized.size),
                vector_to_blob(normalized),
            )
        await db.commit()
        embedded += len(batch)

    return {"embedded": embedded, "model": model_name}


async def _sqlite_vec_similar(
    db: aiosqlite.Connection,
    model_name: str,
    cve_id: str,
    target_blob: bytes,
    limit: int,
) -> list[dict] | None:
    """Optional accelerator. Returns None whenever sqlite-vec is missing or
    the Python/SQLite build cannot load extensions — caller uses NumPy."""
    if sqlite_vec is None:
        return None
    try:
        await db.enable_load_extension(True)
        await db.load_extension(sqlite_vec.loadable_path())
        await db.enable_load_extension(False)
        rows = await db.execute_fetchall(
            """
            SELECT cve_id, vec_distance_cosine(vector, ?) AS dist
            FROM cve_embeddings
            WHERE model = ? AND cve_id != ?
            ORDER BY dist ASC
            LIMIT ?
            """,
            (target_blob, model_name, cve_id.upper(), limit),
        )
        return [
            {"cve_id": row["cve_id"], "similarity": round(1.0 - float(row["dist"]), 4)}
            for row in rows
        ]
    except Exception as exc:
        logger.debug(
            "sqlite-vec accelerator unavailable (%s) — using NumPy brute force", exc
        )
        return None


async def find_similar_cves(
    db: aiosqlite.Connection, cve_id: str, limit: int = 5
) -> list[dict] | None:
    """Top-k semantically similar CVEs by cosine similarity.

    Returns None when the target CVE has no stored vector — the caller must
    fall back to the deterministic shared-product heuristic. No model
    inference happens here: this is a pure scan over stored BLOBs.
    """
    model_name = get_embeddings_model_name()
    target_blob = await get_cve_embedding(db, cve_id, model_name)
    if target_blob is None:
        return None

    accelerated = await _sqlite_vec_similar(db, model_name, cve_id, target_blob, limit)
    if accelerated is not None:
        return accelerated

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
