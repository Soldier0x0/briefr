"""Durable security publications + deterministic entity links (intel schema).

Revision ID: 041_publications
Revises: 040_infra_classifications
"""

from __future__ import annotations

from alembic import op

revision = "041_publications"
down_revision = "040_infra_classifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publications (
            publication_id   SERIAL PRIMARY KEY,
            source_key       TEXT NOT NULL,
            canonical_url    TEXT NOT NULL,
            url_hash         TEXT NOT NULL,
            content_sha256   TEXT NOT NULL DEFAULT '',
            title            TEXT NOT NULL DEFAULT '',
            document_kind    TEXT NOT NULL DEFAULT 'unknown',
            published_at     TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT '',
            retrieved_at     TEXT NOT NULL DEFAULT '',
            canonical_external_id TEXT NOT NULL DEFAULT '',
            language         TEXT NOT NULL DEFAULT '',
            knowledge_state  TEXT NOT NULL DEFAULT 'known',
            extraction_status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE (source_key, canonical_url)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publications_published "
        "ON intel.publications (published_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publications_source "
        "ON intel.publications (source_key)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publications_url_hash "
        "ON intel.publications (url_hash)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publication_entity_links (
            id               SERIAL PRIMARY KEY,
            publication_id   INTEGER NOT NULL,
            entity_type      TEXT NOT NULL,
            entity_id        TEXT NOT NULL,
            extractor        TEXT NOT NULL DEFAULT '',
            evidence_field   TEXT NOT NULL DEFAULT '',
            confidence       TEXT NOT NULL DEFAULT 'medium',
            observed_at      TEXT NOT NULL DEFAULT '',
            retrieved_at     TEXT NOT NULL DEFAULT '',
            UNIQUE (publication_id, entity_type, entity_id, extractor, evidence_field)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publication_entity_links_entity "
        "ON intel.publication_entity_links (entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publication_entity_links_pub "
        "ON intel.publication_entity_links (publication_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS intel.publication_entity_links")
    op.execute("DROP TABLE IF EXISTS intel.publications")
