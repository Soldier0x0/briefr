"""E7 — semantic search stack / severity / kev filters."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db
from services.semantic_search import run_semantic_search
from tests.conftest import run_db_test


def test_semantic_search_stack_filter_narrows_cve_hits(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite filter path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e7-filt.db"))
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, summary, published, severity, is_kev)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2026-E7-NGX",
                    "Remote code execution in nginx reverse proxy",
                    "nginx rce",
                    "2026-02-01",
                    "CRITICAL",
                    1,
                ),
            )
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, summary, published, severity, is_kev)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2026-E7-ORA",
                    "Remote code execution in oracle database",
                    "oracle rce",
                    "2026-02-02",
                    "HIGH",
                    0,
                ),
            )

            wide = await run_semantic_search(
                db, "remote code execution", mode="keyword", limit=10
            )
            ids_wide = {r["entity_id"] for r in wide["data"] if r.get("entity_type") == "cve"}
            assert "CVE-2026-E7-NGX" in ids_wide
            assert "CVE-2026-E7-ORA" in ids_wide

            stacked = await run_semantic_search(
                db,
                "remote code execution",
                mode="keyword",
                limit=10,
                stack="nginx",
            )
            ids_stack = {
                r["entity_id"] for r in stacked["data"] if r.get("entity_type") == "cve"
            }
            assert "CVE-2026-E7-NGX" in ids_stack
            assert "CVE-2026-E7-ORA" not in ids_stack
            assert stacked["meta"]["stack_terms"] == ["nginx"]

            crit = await run_semantic_search(
                db,
                "remote code execution",
                mode="keyword",
                limit=10,
                severity="CRITICAL",
            )
            ids_crit = {r["entity_id"] for r in crit["data"] if r.get("entity_type") == "cve"}
            assert ids_crit == {"CVE-2026-E7-NGX"}

            kev = await run_semantic_search(
                db,
                "remote code execution",
                mode="keyword",
                limit=10,
                kev_only=True,
            )
            ids_kev = {r["entity_id"] for r in kev["data"] if r.get("entity_type") == "cve"}
            assert ids_kev == {"CVE-2026-E7-NGX"}
        finally:
            await db.close()

    run_db_test(run())
