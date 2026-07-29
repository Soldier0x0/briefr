"""CVE description embeddings — env-gated, CPU-only (V1.3 / E2–E3).

**Write path (E2):** dual-write to ``embeddings`` + legacy ``cve_embeddings``.

**Related (E3):** request path uses stored vectors only — pgvector ANN (or
SQLite BLOB cosine) on ``embeddings``, then legacy ``cve_embeddings`` NumPy
scan. No model inference for related.

**Semantic search (E3):** may embed a single query string when
``EMBEDDINGS_ENABLED=1`` (design §7.1). Bulk corpus embedding stays
scheduler-only (``run_embeddings_backfill``).

Disabled by default (``EMBEDDINGS_ENABLED=0``). Set ``EMBEDDINGS_PGVECTOR=0``
to skip writes to the ``embeddings`` table (legacy-only).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
import logging
import os

from catchup_mode import effective_embeddings_max_per_run

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
from db.embeddings_search import find_similar_via_embeddings_table
from db.embeddings_store import (
    embeddings_pgvector_writes_enabled,
    get_campaigns_needing_embeddings,
    get_cves_needing_embeddings,
    get_cves_needing_embeddings_by_ids,
    get_techniques_needing_embeddings,
    upsert_campaign_embedding_row,
    upsert_cve_embedding_row,
    upsert_technique_embedding_row,
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
    # Default on: when embeddings are enabled, keep the index warm after ingest
    # unless the operator explicitly sets EMBEDDINGS_AUTO_ON_INGEST=0.
    return embeddings_enabled() and os.environ.get(
        "EMBEDDINGS_AUTO_ON_INGEST", "1"
    ).strip().lower() in ("1", "true", "yes")


def get_embeddings_ingest_max_per_run() -> int:
    return int(os.environ.get("EMBEDDINGS_INGEST_MAX_PER_RUN", "25"))


def get_embeddings_ingest_skip_queue_depth() -> int:
    return int(os.environ.get("EMBEDDINGS_INGEST_SKIP_QUEUE_DEPTH", "10000"))


async def embeddings_ingest_backlog_should_skip(db) -> bool:
    """Skip NVD ingest-tail embed when the backfill queue is deep."""
    from db.embeddings_store import count_embeddings_pending_missing

    pending = await count_embeddings_pending_missing(db, get_embeddings_model_name())
    return int(pending.get("total") or 0) > get_embeddings_ingest_skip_queue_depth()


def get_embeddings_model_name() -> str:
    return (
        os.environ.get("EMBEDDINGS_MODEL", DEFAULT_EMBEDDINGS_MODEL).strip()
        or DEFAULT_EMBEDDINGS_MODEL
    )


def get_embeddings_max_per_run() -> int:
    base = int(os.environ.get("EMBEDDINGS_MAX_PER_RUN", "2000"))
    return effective_embeddings_max_per_run(base)


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
        for item, vector in zip(batch, vectors, strict=False):
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


async def run_technique_embeddings_backfill(
    db,
    progress_cb=None,
) -> dict:
    """Embed MITRE techniques missing / hash-mismatched (E6). Scheduler-side only."""
    global _missing_dep_logged

    model_name = get_embeddings_model_name()
    if not embeddings_pgvector_writes_enabled():
        return {"embedded": 0, "model": model_name, "skipped": "pgvector writes disabled"}

    cap = get_embeddings_max_per_run()
    # Techniques are a small catalog — allow a dedicated slice of the cap.
    tech_cap = min(cap, 800)
    pending = await get_techniques_needing_embeddings(db, model_name, limit=tech_cap)
    if not pending:
        return {"embedded": 0, "model": model_name}

    if TextEmbedding is None:
        if not _missing_dep_logged:
            logger.warning(
                "EMBEDDINGS_ENABLED=1 but 'fastembed' is not installed — "
                "technique embeddings backfill skipped"
            )
            _missing_dep_logged = True
        return {"embedded": 0, "model": model_name, "skipped": "fastembed missing"}

    model = _get_model(model_name)
    embedded = 0
    total = len(pending)
    total_batches = (total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for batch_num, offset in enumerate(range(0, total, EMBED_BATCH_SIZE), start=1):
        batch = pending[offset : offset + EMBED_BATCH_SIZE]
        if progress_cb:
            progress_cb(
                f"Embedding ATT&CK techniques with {model_name}: "
                f"batch {batch_num}/{total_batches} "
                f"({min(offset + EMBED_BATCH_SIZE, total)}/{total})…"
            )
        texts = [item["embed_text"] for item in batch]
        vectors = await asyncio.to_thread(_embed_texts, model, texts)
        for item, vector in zip(batch, vectors, strict=False):
            normalized = l2_normalize(vector)
            blob = vector_to_blob(normalized)
            dims = int(normalized.size)
            await upsert_technique_embedding_row(
                db,
                item["technique_id"],
                model_name,
                dims,
                blob,
                item["content_hash"],
            )
        await db.commit()
        embedded += len(batch)

    return {"embedded": embedded, "model": model_name}


async def run_campaign_embeddings_backfill(
    db,
    progress_cb=None,
) -> dict:
    """Embed correlation campaigns missing / hash-mismatched (E8). Scheduler-only."""
    global _missing_dep_logged

    model_name = get_embeddings_model_name()
    if not embeddings_pgvector_writes_enabled():
        return {"embedded": 0, "model": model_name, "skipped": "pgvector writes disabled"}

    cap = get_embeddings_max_per_run()
    camp_cap = min(cap, 500)
    pending = await get_campaigns_needing_embeddings(db, model_name, limit=camp_cap)
    if not pending:
        return {"embedded": 0, "model": model_name}

    if TextEmbedding is None:
        if not _missing_dep_logged:
            logger.warning(
                "EMBEDDINGS_ENABLED=1 but 'fastembed' is not installed — "
                "campaign embeddings backfill skipped"
            )
            _missing_dep_logged = True
        return {"embedded": 0, "model": model_name, "skipped": "fastembed missing"}

    model = _get_model(model_name)
    embedded = 0
    total = len(pending)
    total_batches = (total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for batch_num, offset in enumerate(range(0, total, EMBED_BATCH_SIZE), start=1):
        batch = pending[offset : offset + EMBED_BATCH_SIZE]
        if progress_cb:
            progress_cb(
                f"Embedding campaigns with {model_name}: "
                f"batch {batch_num}/{total_batches} "
                f"({min(offset + EMBED_BATCH_SIZE, total)}/{total})…"
            )
        texts = [item["embed_text"] for item in batch]
        vectors = await asyncio.to_thread(_embed_texts, model, texts)
        for item, vector in zip(batch, vectors, strict=False):
            normalized = l2_normalize(vector)
            blob = vector_to_blob(normalized)
            dims = int(normalized.size)
            await upsert_campaign_embedding_row(
                db,
                item["campaign_id"],
                model_name,
                dims,
                blob,
                item["content_hash"],
            )
        await db.commit()
        embedded += len(batch)

    return {"embedded": embedded, "model": model_name}


async def find_similar_cves(db, cve_id: str, limit: int = 5) -> list[dict] | None:
    """Top-k semantically similar CVEs by cosine similarity.

    Prefer the multi-entity ``embeddings`` table (pgvector ANN on Postgres,
    BLOB cosine on SQLite). Fall back to legacy ``cve_embeddings`` NumPy scan.
    Returns None when the target CVE has no stored vector — the caller must
    fall back to the deterministic shared-product heuristic. No model
    inference happens here.
    """
    model_name = get_embeddings_model_name()
    try:
        ann = await find_similar_via_embeddings_table(
            db, cve_id, model_name, limit=limit
        )
    except Exception:
        logger.exception(
            "embeddings-table ANN failed for %s — trying legacy BLOBs", cve_id
        )
        ann = None
    if ann is not None:
        return ann

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


async def embed_query_text(text: str) -> bytes | None:
    """Embed one search query. Returns L2-normalized float32 blob, or None.

    Request-path use is limited to semantic/hybrid search (design §7.1).
    Related CVEs must not call this — they use stored vectors only.
    """
    global _missing_dep_logged
    if not embeddings_enabled():
        return None
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    if TextEmbedding is None:
        if not _missing_dep_logged:
            logger.warning(
                "EMBEDDINGS_ENABLED=1 but 'fastembed' is not installed — "
                "semantic search falls back to keyword"
            )
            _missing_dep_logged = True
        return None
    model_name = get_embeddings_model_name()
    try:

        def _load_and_embed() -> list[np.ndarray]:
            model = _get_model(model_name)
            return _embed_texts(model, [cleaned])

        # Model load + ONNX inference are CPU-heavy — never block the event loop.
        vectors = await asyncio.to_thread(_load_and_embed)
    except Exception:
        logger.exception("query embedding failed")
        return None
    if not vectors:
        return None
    return vector_to_blob(l2_normalize(vectors[0]))
