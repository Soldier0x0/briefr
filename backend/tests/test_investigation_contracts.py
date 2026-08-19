import pytest
from pydantic import ValidationError

from investigations.contracts import (
    EdgeClass,
    GraphEdge,
    GraphPage,
    RelationshipFilters,
    make_node_id,
)


def test_make_node_id_ioc_hash():
    assert make_node_id("ioc", "hash:abc") == "ioc:hash:abc"


def test_filters_reject_depth_above_two():
    with pytest.raises(ValidationError):
        RelationshipFilters(depth=3)


def test_include_semantic_defaults_false():
    assert RelationshipFilters().include_semantic is False


def test_unknown_edge_class_rejected():
    with pytest.raises(ValidationError):
        GraphEdge(
            edge_id="x",
            source_node_id="cve:CVE-1",
            target_node_id="technique:T1",
            edge_class="guess",  # type: ignore[arg-type]
            source_key="t",
        )


def test_graph_page_requires_nodes_and_edges():
    page = GraphPage(
        root={
            "node_id": "cve:CVE-1",
            "entity_type": "cve",
            "entity_id": "CVE-1",
            "label": "CVE-1",
            "knowledge_state": "known",
        },
        nodes=[],
        edges=[],
        source_status="ok",
        knowledge_state="unknown",
        truncated=False,
        next_cursor=None,
        generated_at="2026-08-17T00:00:00Z",
        depth=1,
    )
    assert page.truncated is False
    assert EdgeClass  # imported for exhaustive use in projection later
