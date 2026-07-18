"""Runtime read/write for the multi-entity ``embeddings`` table (E2/E3).

Dual-writes with legacy ``cve_embeddings``. E3 related/search prefer this table
(pgvector ANN on Postgres; BLOB cosine on SQLite).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import os

from db.embeddings_pgvector import (
    ENTITY_TYPE_CVE,
    ENTITY_TYPE_TECHNIQUE,
    blob_to_pgvector_literal,
    build_cve_embed_text,
    build_technique_embed_text,
    content_hash_for_embed_text,
    is_placeholder_content_hash,
)
from db.timeutil import utcnow_str
from db.types import DbConnection

_UPSERT_EMBEDDING_SQLITE = """
INSERT INTO embeddings (
    entity_type, entity_id, model, dims, embedding, content_hash, updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(entity_type, entity_id, model) DO UPDATE SET
    dims = excluded.dims,
    embedding = excluded.embedding,
    content_hash = excluded.content_hash,
    updated_at = excluded.updated_at
"""

_UPSERT_EMBEDDING_PG = """
INSERT INTO embeddings (
    entity_type, entity_id, model, dims, embedding, content_hash, updated_at
)
VALUES (
    $1, $2, $3, $4, CAST($5 AS vector), $6, NOW()
)
ON CONFLICT (entity_type, entity_id, model) DO UPDATE SET
    dims = EXCLUDED.dims,
    embedding = EXCLUDED.embedding,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW()
"""

# Missing row OR E1 migrated: placeholder — newest CVEs first.
_GET_CVES_NEEDING_EMBEDDINGS_SQLITE = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM cves c
LEFT JOIN embeddings e
  ON e.entity_type = 'cve' AND e.entity_id = c.cve_id AND e.model = ?
WHERE c.description IS NOT NULL
  AND c.description != ''
  AND (
    e.entity_id IS NULL
    OR e.content_hash LIKE 'migrated:%'
  )
ORDER BY c.published DESC
LIMIT ?
"""

_GET_CVES_NEEDING_EMBEDDINGS_PG = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM cves c
LEFT JOIN embeddings e
  ON e.entity_type = 'cve' AND e.entity_id = c.cve_id AND e.model = $1
WHERE c.description IS NOT NULL
  AND c.description != ''
  AND (
    e.entity_id IS NULL
    OR e.content_hash LIKE 'migrated:%'
  )
ORDER BY c.published DESC
LIMIT $2
"""

# Oldest existing embeds first — Python `_row_to_pending` drops fresh hashes.
_GET_CVES_FOR_HASH_RESYNC_SQLITE = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM embeddings e
INNER JOIN cves c ON c.cve_id = e.entity_id
WHERE e.entity_type = 'cve'
  AND e.model = ?
  AND e.content_hash NOT LIKE 'migrated:%'
  AND c.description IS NOT NULL
  AND c.description != ''
ORDER BY e.updated_at ASC
LIMIT ?
"""

_GET_CVES_FOR_HASH_RESYNC_PG = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM embeddings e
INNER JOIN cves c ON c.cve_id = e.entity_id
WHERE e.entity_type = 'cve'
  AND e.model = $1
  AND e.content_hash NOT LIKE 'migrated:%'
  AND c.description IS NOT NULL
  AND c.description != ''
ORDER BY e.updated_at ASC NULLS LAST
LIMIT $2
"""

_GET_CVES_BY_IDS_SQLITE = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM cves c
LEFT JOIN embeddings e
  ON e.entity_type = 'cve' AND e.entity_id = c.cve_id AND e.model = ?
WHERE c.cve_id IN ({placeholders})
"""

_GET_CVES_BY_IDS_PG = """
SELECT c.cve_id, c.description, c.summary, c.affected_products, c.cwe_ids,
       e.content_hash AS existing_hash
FROM cves c
LEFT JOIN embeddings e
  ON e.entity_type = 'cve' AND e.entity_id = c.cve_id AND e.model = $1
WHERE c.cve_id IN ({placeholders})
"""


def _is_postgres_connection(db: DbConnection) -> bool:
    return type(db).__name__ == "PostgresConnection"


def embeddings_pgvector_writes_enabled() -> bool:
    """Write to ``embeddings`` unless explicitly disabled.

    Default on: E1 migration + extension (or SQLite BLOB shim) is the storage
    target for new vectors. Set ``EMBEDDINGS_PGVECTOR=0`` to legacy-only writes.
    """
    return os.environ.get("EMBEDDINGS_PGVECTOR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


async def upsert_embedding_row(
    db: DbConnection,
    *,
    entity_type: str,
    entity_id: str,
    model: str,
    dims: int,
    vector_blob: bytes,
    content_hash: str,
) -> None:
    """Upsert one row into ``embeddings`` (BLOB on SQLite, vector on Postgres)."""
    pg = _is_postgres_connection(db)
    if pg:
        literal = blob_to_pgvector_literal(vector_blob, expected_dim=dims)
        if literal is None:
            raise ValueError(
                f"invalid embedding blob for {entity_type}/{entity_id} dims={dims}"
            )
        await db.execute(
            _UPSERT_EMBEDDING_PG,
            (entity_type, entity_id, model, dims, literal, content_hash),
        )
    else:
        await db.execute(
            _UPSERT_EMBEDDING_SQLITE,
            (
                entity_type,
                entity_id,
                model,
                dims,
                vector_blob,
                content_hash,
                utcnow_str(),
            ),
        )


async def upsert_cve_embedding_row(
    db: DbConnection,
    cve_id: str,
    model: str,
    dims: int,
    vector_blob: bytes,
    content_hash: str,
) -> None:
    await upsert_embedding_row(
        db,
        entity_type=ENTITY_TYPE_CVE,
        entity_id=cve_id.upper(),
        model=model,
        dims=dims,
        vector_blob=vector_blob,
        content_hash=content_hash,
    )


def _row_to_pending(row: dict, model: str) -> dict | None:
    text = build_cve_embed_text(
        description=row.get("description"),
        summary=row.get("summary"),
        affected_products=row.get("affected_products"),
        cwe_ids=row.get("cwe_ids"),
    )
    if not text.strip():
        return None
    new_hash = content_hash_for_embed_text(text, model)
    existing = row.get("existing_hash")
    if existing and not is_placeholder_content_hash(existing) and existing == new_hash:
        return None
    return {
        "cve_id": row["cve_id"],
        "description": row.get("description") or "",
        "embed_text": text,
        "content_hash": new_hash,
        "existing_hash": existing,
    }


async def get_cves_needing_embeddings(
    db: DbConnection, model: str, limit: int = 500
) -> list[dict]:
    """CVEs missing / migrated / content_hash drift (E7 freshness).

    1) Prefer never-embedded or ``migrated:`` placeholders (newest CVEs first).
    2) Fill remaining budget by scanning oldest existing embeds for hash drift
       so description/summary updates are not stuck forever after first embed.
    """
    capped = max(1, int(limit))
    pg = _is_postgres_connection(db)
    sql = _GET_CVES_NEEDING_EMBEDDINGS_PG if pg else _GET_CVES_NEEDING_EMBEDDINGS_SQLITE
    rows = await db.execute_fetchall(sql, (model, capped))
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        item = _row_to_pending(dict(row), model)
        if not item:
            continue
        cid = item["cve_id"]
        if cid in seen:
            continue
        seen.add(cid)
        out.append(item)
        if len(out) >= capped:
            return out

    remaining = capped - len(out)
    if remaining <= 0:
        return out

    # Over-fetch: many oldest rows may still be hash-fresh.
    # Bound the scan so a large remaining budget cannot stall the event loop.
    scan = min(max(remaining * 8, remaining), 2000)
    resync_sql = (
        _GET_CVES_FOR_HASH_RESYNC_PG if pg else _GET_CVES_FOR_HASH_RESYNC_SQLITE
    )
    resync_rows = await db.execute_fetchall(resync_sql, (model, scan))
    for row in resync_rows:
        item = _row_to_pending(dict(row), model)
        if not item:
            continue
        cid = item["cve_id"]
        if cid in seen:
            continue
        seen.add(cid)
        out.append(item)
        if len(out) >= capped:
            break
    return out


async def get_cves_needing_embeddings_by_ids(
    db: DbConnection, model: str, cve_ids: set[str]
) -> list[dict]:
    """Auto-on-ingest path: re-embed when missing, migrated, or content_hash mismatch."""
    if not cve_ids:
        return []
    # Filter empties/whitespace so we never build `IN ()` (invalid SQL).
    normalized = sorted({c.strip().upper() for c in cve_ids if c and str(c).strip()})
    if not normalized:
        return []
    pg = _is_postgres_connection(db)
    if pg:
        # $1 = model; CVE ids start at $2
        placeholders = ", ".join(f"${i}" for i in range(2, len(normalized) + 2))
        sql = _GET_CVES_BY_IDS_PG.format(placeholders=placeholders)
        rows = await db.execute_fetchall(sql, (model, *normalized))
    else:
        placeholders = ", ".join("?" for _ in normalized)
        sql = _GET_CVES_BY_IDS_SQLITE.format(placeholders=placeholders)
        rows = await db.execute_fetchall(sql, (model, *normalized))
    out: list[dict] = []
    for row in rows:
        item = _row_to_pending(dict(row), model)
        if item:
            out.append(item)
    return out


_GET_TECHNIQUES_NEEDING_SQLITE = """
SELECT t.technique_id, t.name, t.description, t.tactic,
       e.content_hash AS existing_hash
FROM mitre_techniques t
LEFT JOIN embeddings e
  ON e.entity_type = 'technique' AND e.entity_id = t.technique_id AND e.model = ?
ORDER BY t.technique_id
"""

_GET_TECHNIQUES_NEEDING_PG = """
SELECT t.technique_id, t.name, t.description, t.tactic,
       e.content_hash AS existing_hash
FROM mitre_techniques t
LEFT JOIN embeddings e
  ON e.entity_type = 'technique' AND e.entity_id = t.technique_id AND e.model = $1
ORDER BY t.technique_id
"""


def _technique_row_to_pending(row: dict, model: str) -> dict | None:
    text = build_technique_embed_text(
        name=row.get("name"),
        description=row.get("description"),
        tactic=row.get("tactic"),
    )
    if not text.strip():
        return None
    new_hash = content_hash_for_embed_text(text, model)
    existing = row.get("existing_hash")
    if existing and not is_placeholder_content_hash(existing) and existing == new_hash:
        return None
    return {
        "technique_id": row["technique_id"],
        "embed_text": text,
        "content_hash": new_hash,
        "existing_hash": existing,
    }


async def upsert_technique_embedding_row(
    db: DbConnection,
    technique_id: str,
    model: str,
    dims: int,
    vector_blob: bytes,
    content_hash: str,
) -> None:
    await upsert_embedding_row(
        db,
        entity_type=ENTITY_TYPE_TECHNIQUE,
        entity_id=str(technique_id).upper(),
        model=model,
        dims=dims,
        vector_blob=vector_blob,
        content_hash=content_hash,
    )


async def get_techniques_needing_embeddings(
    db: DbConnection, model: str, limit: int = 500
) -> list[dict]:
    """Techniques missing / placeholder / content_hash mismatch (ATT&CK refresh).

    Scans the full ATT&CK catalog (hundreds of rows) so early up-to-date IDs
    cannot starve later techniques (Gemini #676).
    """
    pg = _is_postgres_connection(db)
    sql = _GET_TECHNIQUES_NEEDING_PG if pg else _GET_TECHNIQUES_NEEDING_SQLITE
    rows = await db.execute_fetchall(sql, (model,))
    out: list[dict] = []
    for row in rows:
        item = _technique_row_to_pending(dict(row), model)
        if item:
            out.append(item)
        if len(out) >= limit:
            break
    return out
