"""Golden query contract tests for the retrieval engine (E7)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.embeddings_search import classify_query_shape

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "retrieval_golden_queries.json"


def test_golden_query_shapes_match_classifier():
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data["queries"], "golden fixture must not be empty"
    for row in data["queries"]:
        shape = classify_query_shape(row["q"])
        assert shape == row["expect_shape"], row["id"]
