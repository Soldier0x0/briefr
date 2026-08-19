"""Discovered publication actors (source-qualified ids)."""

from __future__ import annotations

import re

from db.timeutil import utcnow_str
from db.types import DbConnection

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def actor_slug(display_name: str) -> str:
    slug = _SLUG_RE.sub("-", display_name.strip().lower()).strip("-")
    return slug[:80] or "unknown"


def make_actor_id(source_key: str, display_name: str) -> str:
    return f"{source_key}:author:{actor_slug(display_name)}"


async def upsert_publication_actor(
    db: DbConnection,
    *,
    source_key: str,
    display_name: str,
    actor_kind: str = "contributor",
    profile_url: str = "",
) -> str | None:
    name = (display_name or "").strip()
    if not name:
        return None
    actor_id = make_actor_id(source_key, name)
    now = utcnow_str()
    await db.execute(
        """
        INSERT INTO publication_actors (
            actor_id, source_key, display_name, actor_kind, profile_url,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(actor_id) DO UPDATE SET
            display_name = excluded.display_name,
            profile_url = CASE
                WHEN excluded.profile_url != '' THEN excluded.profile_url
                ELSE publication_actors.profile_url
            END,
            updated_at = excluded.updated_at
        """,
        (actor_id, source_key, name, actor_kind, profile_url or "", now, now),
    )
    return actor_id


async def link_publication_actor(
    db: DbConnection,
    publication_id: int,
    actor_id: str,
    *,
    observed_at: str,
) -> None:
    now = observed_at or utcnow_str()
    await db.execute(
        """
        INSERT INTO publication_actor_links (
            publication_id, actor_id, extractor, evidence_field,
            confidence, observed_at
        ) VALUES (?, ?, 'metadata_author', 'author', 'medium', ?)
        ON CONFLICT(publication_id, actor_id, extractor) DO UPDATE SET
            observed_at = excluded.observed_at
        """,
        (publication_id, actor_id, now),
    )
