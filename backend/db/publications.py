"""Publication persistence helpers (intel.publications tables)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from db.timeutil import utcnow_str
from db.types import DbConnection
from publications.extract import extract_cve_ids, extract_technique_ids

_URL_HASH_LEN = 32


def url_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.strip().encode("utf-8")).hexdigest()[:_URL_HASH_LEN]


def publication_row_to_dict(row: Any, cve_ids: list[str] | None = None) -> dict[str, Any]:
    data = {
        "publication_id": row["publication_id"],
        "source_key": row["source_key"],
        "canonical_url": row["canonical_url"],
        "title": row["title"],
        "document_kind": row["document_kind"],
        "published_at": row["published_at"],
        "updated_at": row["updated_at"],
        "retrieved_at": row["retrieved_at"],
        "canonical_external_id": row["canonical_external_id"],
        "language": row["language"],
        "knowledge_state": row["knowledge_state"],
        "extraction_status": row["extraction_status"],
        "content_sha256": row["content_sha256"],
    }
    if cve_ids is not None:
        data["cve_ids"] = cve_ids
    return data


async def get_headline_url_set(db: DbConnection) -> set[str]:
    """URLs from the incident feed snapshot (Headlines lane), for dedup badges."""
    from feeds.case_study_feed import SNAPSHOT_CACHE_KEY

    raw = await db.execute_fetchall(
        "SELECT result FROM feed_cache WHERE cache_key = ?",
        (SNAPSHOT_CACHE_KEY,),
    )
    if not raw:
        return set()
    try:
        payload = json.loads(raw[0]["result"])
    except (json.JSONDecodeError, TypeError, KeyError):
        return set()
    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list):
        return set()
    urls: set[str] = set()
    for card in cards:
        if not isinstance(card, dict) or card.get("kind") == "atlas":
            continue
        url = (card.get("url") or card.get("id") or "").strip()
        if url:
            urls.add(url)
    return urls


def _mark_headline_overlap(rows: list[dict[str, Any]], headline_urls: set[str]) -> list[dict[str, Any]]:
    if not headline_urls:
        return rows
    for row in rows:
        row["also_in_headlines"] = row.get("canonical_url") in headline_urls
    return rows


async def upsert_publication(
    db: DbConnection,
    *,
    source_key: str,
    canonical_url: str,
    content_sha256: str,
    title: str,
    document_kind: str,
    published_at: str,
    updated_at: str,
    retrieved_at: str,
    canonical_external_id: str = "",
    language: str = "",
    knowledge_state: str = "known",
    extraction_status: str = "complete",
) -> tuple[int, bool]:
    """Insert or refresh one publication row. Returns (publication_id, is_new)."""
    canonical = canonical_url.strip()
    if not canonical:
        raise ValueError("canonical_url required")
    url_digest = url_hash(canonical)
    now = retrieved_at or utcnow_str()

    existing = await db.execute_fetchall(
        """
        SELECT publication_id, content_sha256
        FROM publications
        WHERE source_key = ? AND canonical_url = ?
        """,
        (source_key, canonical),
    )
    if existing:
        pub_id = int(existing[0]["publication_id"])
        await db.execute(
            """
            UPDATE publications SET
                url_hash = ?,
                content_sha256 = ?,
                title = ?,
                document_kind = ?,
                published_at = ?,
                updated_at = ?,
                retrieved_at = ?,
                canonical_external_id = ?,
                language = ?,
                knowledge_state = ?,
                extraction_status = ?
            WHERE publication_id = ?
            """,
            (
                url_digest,
                content_sha256,
                title,
                document_kind,
                published_at,
                updated_at,
                now,
                canonical_external_id,
                language,
                knowledge_state,
                extraction_status,
                pub_id,
            ),
        )
        return pub_id, False

    await db.execute(
        """
        INSERT INTO publications (
            source_key, canonical_url, url_hash, content_sha256, title,
            document_kind, published_at, updated_at, retrieved_at,
            canonical_external_id, language, knowledge_state, extraction_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_key,
            canonical,
            url_digest,
            content_sha256,
            title,
            document_kind,
            published_at,
            updated_at,
            now,
            canonical_external_id,
            language,
            knowledge_state,
            extraction_status,
        ),
    )
    row = await db.execute_fetchall(
        "SELECT publication_id FROM publications WHERE source_key = ? AND canonical_url = ?",
        (source_key, canonical),
    )
    return int(row[0]["publication_id"]), True


async def replace_publication_entity_links(
    db: DbConnection,
    publication_id: int,
    *,
    title: str,
    body: str,
    retrieved_at: str,
) -> int:
    """Run deterministic extractors and replace entity links for one publication."""
    await db.execute(
        "DELETE FROM publication_entity_links WHERE publication_id = ?",
        (publication_id,),
    )
    written = 0
    now = retrieved_at or utcnow_str()

    for cve_id in extract_cve_ids(title, body):
        await db.execute(
            """
            INSERT INTO publication_entity_links (
                publication_id, entity_type, entity_id, extractor,
                evidence_field, confidence, observed_at, retrieved_at
            ) VALUES (?, 'cve', ?, 'regex_cve', 'title+body', 'high', ?, ?)
            """,
            (publication_id, cve_id, now, now),
        )
        written += 1

    for technique_id in extract_technique_ids(title, body):
        await db.execute(
            """
            INSERT INTO publication_entity_links (
                publication_id, entity_type, entity_id, extractor,
                evidence_field, confidence, observed_at, retrieved_at
            ) VALUES (?, 'technique', ?, 'regex_attack', 'title+body', 'medium', ?, ?)
            """,
            (publication_id, technique_id, now, now),
        )
        written += 1

    return written


async def list_publications(
    db: DbConnection,
    *,
    cve_id: str | None = None,
    source_key: str | None = None,
    document_kind: str | None = None,
    q: str | None = None,
    limit: int = 50,
    cursor: int | None = None,
    mark_headlines: bool = False,
) -> tuple[list[dict[str, Any]], int | None]:
    """List publications with optional filters. Returns rows and next cursor."""
    clauses: list[str] = []
    params: list[Any] = []

    if cve_id:
        clauses.append(
            """
            publication_id IN (
                SELECT publication_id FROM publication_entity_links
                WHERE entity_type = 'cve' AND entity_id = ?
            )
            """
        )
        params.append(cve_id.upper())

    if source_key:
        clauses.append("source_key = ?")
        params.append(source_key.strip())

    if document_kind:
        clauses.append("document_kind = ?")
        params.append(document_kind.strip())

    if q:
        clauses.append("title LIKE ?")
        params.append(f"%{q.strip()}%")

    if cursor is not None:
        clauses.append("publication_id < ?")
        params.append(cursor)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit + 1)

    rows = await db.execute_fetchall(
        f"""
        SELECT publication_id, source_key, canonical_url, title, document_kind,
               published_at, updated_at, retrieved_at, canonical_external_id,
               language, knowledge_state, extraction_status, content_sha256
        FROM publications
        {where}
        ORDER BY publication_id DESC
        LIMIT ?
        """,
        tuple(params),
    )

    next_cursor: int | None = None
    if len(rows) > limit:
        next_cursor = int(rows[limit - 1]["publication_id"])
        rows = rows[:limit]

    pub_ids = [int(r["publication_id"]) for r in rows]
    cve_map: dict[int, list[str]] = {pid: [] for pid in pub_ids}
    if pub_ids:
        placeholders = ",".join("?" for _ in pub_ids)
        link_rows = await db.execute_fetchall(
            f"""
            SELECT publication_id, entity_id
            FROM publication_entity_links
            WHERE entity_type = 'cve' AND publication_id IN ({placeholders})
            ORDER BY entity_id
            """,
            tuple(pub_ids),
        )
        for link in link_rows:
            pid = int(link["publication_id"])
            cve_map.setdefault(pid, []).append(link["entity_id"])

    data = [
        publication_row_to_dict(row, cve_ids=cve_map.get(int(row["publication_id"]), []))
        for row in rows
    ]
    if mark_headlines:
        headline_urls = await get_headline_url_set(db)
        data = _mark_headline_overlap(data, headline_urls)
    return data, next_cursor


async def get_publication(db: DbConnection, publication_id: int) -> dict[str, Any] | None:
    rows = await db.execute_fetchall(
        """
        SELECT publication_id, source_key, canonical_url, title, document_kind,
               published_at, updated_at, retrieved_at, canonical_external_id,
               language, knowledge_state, extraction_status, content_sha256
        FROM publications
        WHERE publication_id = ?
        """,
        (publication_id,),
    )
    if not rows:
        return None

    links = await db.execute_fetchall(
        """
        SELECT entity_type, entity_id, extractor, evidence_field, confidence,
               observed_at, retrieved_at
        FROM publication_entity_links
        WHERE publication_id = ?
        ORDER BY entity_type, entity_id
        """,
        (publication_id,),
    )
    cve_ids = [r["entity_id"] for r in links if r["entity_type"] == "cve"]
    payload = publication_row_to_dict(rows[0], cve_ids=cve_ids)
    payload["entity_links"] = [
        {
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "extractor": r["extractor"],
            "evidence_field": r["evidence_field"],
            "confidence": r["confidence"],
            "observed_at": r["observed_at"],
            "retrieved_at": r["retrieved_at"],
        }
        for r in links
    ]
    actor_rows = await db.execute_fetchall(
        """
        SELECT a.actor_id, a.display_name, a.actor_kind, a.profile_url,
               l.extractor, l.evidence_field, l.confidence, l.observed_at
        FROM publication_actor_links l
        JOIN publication_actors a ON a.actor_id = l.actor_id
        WHERE l.publication_id = ?
        ORDER BY a.display_name
        """,
        (publication_id,),
    )
    payload["actors"] = [
        {
            "actor_id": r["actor_id"],
            "display_name": r["display_name"],
            "actor_kind": r["actor_kind"],
            "profile_url": r["profile_url"],
            "extractor": r["extractor"],
            "evidence_field": r["evidence_field"],
            "confidence": r["confidence"],
            "observed_at": r["observed_at"],
        }
        for r in actor_rows
    ]
    headline_urls = await get_headline_url_set(db)
    payload["also_in_headlines"] = rows[0]["canonical_url"] in headline_urls
    return payload


async def get_publications_for_cve(
    db: DbConnection,
    cve_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows, _ = await list_publications(
        db,
        cve_id=cve_id.upper(),
        limit=limit,
        cursor=None,
    )
    return rows
