"""Validate Security Architecture Corpus files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from security_architecture.corpus_loader import load_corpus, reload_corpus


def test_corpus_loads_and_validates():
    corpus = reload_corpus()
    assert corpus.manifest["schema_version"]
    assert len(corpus.components) >= 10
    assert len(corpus.controls) >= 10
    assert len(corpus.trust_boundaries) >= 3
    assert corpus.architecture_graph.get("nodes")
    assert corpus.attack_surface_graph.get("score") is not None


def test_corpus_entity_ids_unique():
    corpus = load_corpus()
    index = corpus.entity_index()
    assert "frontend" in index
    assert "jwt-session" in index
    assert index["frontend"]["_entity_type"] == "component"


def test_stride_matrix_has_stride_categories():
    corpus = load_corpus()
    assert corpus.stride
    threats = corpus.stride[0]["threats"]
    categories = {t["category"] for t in threats}
    assert "spoofing" in categories
    assert "elevation_of_privilege" in categories
