"""Fixture-backed projection hops for investigation graph APIs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test, use_sqlite_backend

from correlation.campaigns import build_campaigns_from_pulses
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database
from investigations.contracts import EdgeClass, RelationshipFilters
from investigations.projection import expand_relationships, get_entity
from investigations.resolve import parse_investigation_query


async def _seed_projection_db(db) -> str:
    await db.execute(
        """
        INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
        VALUES ('CVE-2024-9001', 'Investigation seed', '2024-01-01', 0, 0, 0.5)
        """
    )
    await db.execute(
        """
        INSERT INTO mitre_techniques (technique_id, name, tactic, url)
        VALUES ('T1059.003', 'Command and Scripting Interpreter: Windows Command Shell', 'execution', '')
        """
    )
    await db.execute(
        """
        INSERT INTO cve_technique_map (cve_id, technique_id)
        VALUES ('CVE-2024-9001', 'T1059.003')
        """
    )
    pulses = [
        {
            "pulse_id": "pulse-investigation-1",
            "pulse_name": "Investigation pulse",
            "author": "analyst",
            "created_date": "2024-01-10",
            "adversary": "APT-TEST",
            "malware_families": [],
            "tags": [],
            "targeted_countries": [],
            "ioc_count": 1,
        }
    ]
    await replace_otx_cve_pulses(db, "CVE-2024-9001", pulses)
    await replace_otx_pulse_iocs(
        db,
        "pulse-investigation-1",
        [
            {
                "ioc_type": "domain",
                "ioc_value": "evil.investigation.example",
                "description": "",
            }
        ],
    )
    await build_campaigns_from_pulses(db)
    await db.commit()
    return "CVE-2024-9001"


def test_get_entity_returns_cve(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            cve_id = await _seed_projection_db(db)
            ref = await get_entity(db, "cve", cve_id)
            assert ref is not None
            assert ref.entity_id == cve_id
        finally:
            await db.close()

    run_db_test(run())


def test_expand_cve_includes_technique_and_otx_ioc(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection-hops.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            cve_id = await _seed_projection_db(db)
            root = parse_investigation_query(cve_id)
            page = await expand_relationships(
                db,
                root,
                RelationshipFilters(depth=1, limit=50),
            )
            assert page.root.node_id == f"cve:{cve_id}"
            edge_classes = {edge.edge_class for edge in page.edges}
            source_keys = {edge.source_key for edge in page.edges}
            assert EdgeClass.DIRECT_FACT in edge_classes
            assert EdgeClass.REPORTED in edge_classes
            assert "cve_technique_map" in source_keys
            assert "otx" in source_keys
            assert any(edge.target_node_id.startswith("technique:") for edge in page.edges)
            assert any(edge.target_node_id.startswith("ioc:") for edge in page.edges)
        finally:
            await db.close()

    run_db_test(run())


def test_expand_truncates_when_limit_hit(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection-trunc.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            cve_id = await _seed_projection_db(db)
            root = parse_investigation_query(cve_id)
            page = await expand_relationships(
                db,
                root,
                RelationshipFilters(depth=1, limit=1),
            )
            assert page.truncated is True
            assert page.next_cursor is not None
            assert len(page.edges) == 1
            assert page.root.node_id in {node.node_id for node in page.nodes}
        finally:
            await db.close()

    run_db_test(run())


def test_get_entity_technique_prefers_mitre_name(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection-technique.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            await _seed_projection_db(db)
            ref = await get_entity(db, "technique", "T1059.003")
            assert ref is not None
            assert "Command and Scripting" in ref.label
        finally:
            await db.close()

    run_db_test(run())


def test_stale_cursor_advances_by_edge_id_order(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection-cursor.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            cve_id = await _seed_projection_db(db)
            root = parse_investigation_query(cve_id)
            first = await expand_relationships(
                db,
                root,
                RelationshipFilters(depth=1, limit=1),
            )
            assert first.next_cursor
            from investigations.projection import _encode_cursor

            stale = _encode_cursor({"after_edge_id": "aaa"})
            page = await expand_relationships(
                db,
                root,
                RelationshipFilters(depth=1, limit=1, cursor=stale),
            )
            assert page.edges
            assert page.edges[0].edge_id == first.edges[0].edge_id
        finally:
            await db.close()

    run_db_test(run())


def test_expand_cve_includes_publication_hop(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "projection-pub.db")
        use_sqlite_backend(monkeypatch, db_path)
        await init_db()
        db = await database.get_db()
        try:
            cve_id = await _seed_projection_db(db)
            from db.publications import replace_publication_entity_links, upsert_publication

            pub_id, _ = await upsert_publication(
                db,
                source_key="cisa-news",
                canonical_url="https://example.com/investigation-advisory",
                content_sha256="pubsha",
                title="Advisory for CVE-2024-9001",
                document_kind="advisory",
                published_at="2024-01-15T00:00:00+00:00",
                updated_at="2024-01-15T00:00:00+00:00",
                retrieved_at="2024-01-15T00:00:00+00:00",
            )
            await replace_publication_entity_links(
                db,
                pub_id,
                title="Advisory for CVE-2024-9001",
                body="",
                retrieved_at="2024-01-15T00:00:00+00:00",
            )
            await db.commit()

            root = parse_investigation_query(cve_id)
            page = await expand_relationships(
                db,
                root,
                RelationshipFilters(depth=1, limit=50),
            )
            pub_edges = [
                edge
                for edge in page.edges
                if edge.target_node_id == f"publication:{pub_id}"
            ]
            assert len(pub_edges) == 1
            assert pub_edges[0].edge_class == EdgeClass.REPORTED
            assert pub_edges[0].source_key == "publication:cisa-news"

            pub_ref = await get_entity(db, "publication", str(pub_id))
            assert pub_ref is not None
            assert pub_ref.label == "Advisory for CVE-2024-9001"

            pub_page = await expand_relationships(
                db,
                pub_ref,
                RelationshipFilters(depth=1, limit=50),
            )
            assert any(
                edge.target_node_id == f"cve:{cve_id}" for edge in pub_page.edges
            )
        finally:
            await db.close()

    run_db_test(run())


def test_candidate_edge_coerces_postgres_timestamps():
    from datetime import datetime, timezone

    from investigations.contracts import EntityRef
    from investigations.projection import _candidate_edge

    dt = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
    ref = EntityRef(entity_type="cve", entity_id="CVE-2024-9001", label="CVE-2024-9001")
    candidate = _candidate_edge(
        source_node_id="cve:CVE-2024-ROOT",
        target_ref=ref,
        edge_class=EdgeClass.REPORTED,
        source_key="otx",
        observed_at=dt,
        fetched_at=dt,
    )
    assert candidate.edge.observed_at == "2024-06-15T12:30:00Z"
    assert candidate.edge.fetched_at == "2024-06-15T12:30:00Z"
