"""Embeddings E8 — correlation campaign embeddings + keyword search."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db
from db.embeddings_pgvector import (
    ENTITY_TYPE_CAMPAIGN,
    build_campaign_embed_text,
    content_hash_for_embed_text,
)
from db.embeddings_search import keyword_search_campaigns
from db.embeddings_store import (
    get_campaigns_needing_embeddings,
    upsert_campaign_embedding_row,
)
from ml.embeddings import l2_normalize, vector_to_blob
from tests.conftest import run_db_test

MODEL = "BAAI/bge-small-en-v1.5"


def test_build_campaign_embed_text():
    text = build_campaign_embed_text(
        label="APT29 cloud spearphish",
        adversary="APT29",
        malware_families='["Cobalt Strike"]',
        tags='["espionage", "cloud"]',
    )
    assert "APT29" in text
    assert "Cobalt Strike" in text
    assert "cloud" in text
    h = content_hash_for_embed_text(text, MODEL)
    assert len(h) == 64


def test_campaign_pending_and_upsert_preserves_case(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e8.db"))
    monkeypatch.setenv("EMBEDDINGS_MODEL", MODEL)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO correlation_campaigns (
                    campaign_id, label, adversary, malware_families, tags,
                    confidence, member_count, lifecycle
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "camp_ab12cd34ef56",
                    "APT29 cloud spearphish",
                    "APT29",
                    '["Cobalt Strike"]',
                    '["espionage"]',
                    "high",
                    3,
                    "active",
                ),
            )
            await db.execute(
                """
                INSERT INTO correlation_campaigns (
                    campaign_id, label, adversary, malware_families, tags,
                    confidence, member_count, lifecycle, retracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "camp_retracted99",
                    "Old noise",
                    "unknown",
                    "[]",
                    "[]",
                    "low",
                    2,
                    "stale",
                    "2026-01-01",
                ),
            )
            await db.commit()

            pending = await get_campaigns_needing_embeddings(db, MODEL, limit=10)
            assert any(p["campaign_id"] == "camp_ab12cd34ef56" for p in pending)
            assert not any(p["campaign_id"] == "camp_retracted99" for p in pending)

            item = next(p for p in pending if p["campaign_id"] == "camp_ab12cd34ef56")
            blob = vector_to_blob(l2_normalize(np.array([1.0, 0.0, 0.0], dtype="<f4")))
            await upsert_campaign_embedding_row(
                db, "camp_ab12cd34ef56", MODEL, 3, blob, item["content_hash"]
            )
            await db.commit()

            pending2 = await get_campaigns_needing_embeddings(db, MODEL, limit=10)
            assert not any(p["campaign_id"] == "camp_ab12cd34ef56" for p in pending2)

            rows = await db.execute_fetchall(
                "SELECT entity_type, entity_id FROM embeddings WHERE entity_id = ?",
                ("camp_ab12cd34ef56",),
            )
            assert rows[0]["entity_type"] == ENTITY_TYPE_CAMPAIGN
            assert rows[0]["entity_id"] == "camp_ab12cd34ef56"

            hits = await keyword_search_campaigns(db, "APT29", limit=10)
            assert any(h["campaign_id"] == "camp_ab12cd34ef56" for h in hits)
            return True
        finally:
            await db.close()

    assert run_db_test(run()) is True
