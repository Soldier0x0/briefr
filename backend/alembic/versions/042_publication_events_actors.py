"""Publication events and discovered actors (Milestone C).

Revision ID: 042_publication_events_actors
Revises: 041_publications
"""

from __future__ import annotations

from alembic import op

revision = "042_publication_events_actors"
down_revision = "041_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publication_events (
            event_id         SERIAL PRIMARY KEY,
            source_key       TEXT NOT NULL DEFAULT '',
            title            TEXT NOT NULL DEFAULT '',
            event_kind       TEXT NOT NULL DEFAULT 'other',
            starts_at        TEXT NOT NULL DEFAULT '',
            ends_at          TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT ''
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publication_events_source "
        "ON intel.publication_events (source_key)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publication_event_members (
            event_id         INTEGER NOT NULL,
            publication_id   INTEGER NOT NULL,
            PRIMARY KEY (event_id, publication_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publication_actors (
            actor_id         TEXT PRIMARY KEY,
            source_key       TEXT NOT NULL,
            display_name     TEXT NOT NULL DEFAULT '',
            actor_kind       TEXT NOT NULL DEFAULT 'contributor',
            profile_url      TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT ''
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_publication_actors_source "
        "ON intel.publication_actors (source_key)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS intel.publication_actor_links (
            publication_id   INTEGER NOT NULL,
            actor_id         TEXT NOT NULL,
            extractor        TEXT NOT NULL DEFAULT 'metadata_author',
            evidence_field   TEXT NOT NULL DEFAULT 'author',
            confidence       TEXT NOT NULL DEFAULT 'medium',
            observed_at      TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (publication_id, actor_id, extractor)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS intel.publication_actor_links")
    op.execute("DROP TABLE IF EXISTS intel.publication_actors")
    op.execute("DROP TABLE IF EXISTS intel.publication_event_members")
    op.execute("DROP TABLE IF EXISTS intel.publication_events")
