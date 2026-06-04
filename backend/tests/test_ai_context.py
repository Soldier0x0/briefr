"""Tests for AI/ML CVE context and ATLAS hint mapping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.ai_context import (
    analyze_cve_ai_context,
    cve_matches_declared_frameworks,
    infer_atlas_technique_ids,
)
from feeds.mitre import AI_ML_KEYWORDS


def test_ai_ml_keywords_non_empty():
    assert "tensorflow" in AI_ML_KEYWORDS
    assert "pytorch" in AI_ML_KEYWORDS


def test_detect_tensorflow_sets_ai_context():
    has_ai, tids = analyze_cve_ai_context(
        {
            "description": "Remote code execution in TensorFlow serving.",
            "affected_products": ["cpe:2.3:a:google:tensorflow:*:*:*:*:*:*:*:*"],
        }
    )
    assert has_ai is True
    assert "AML.T0040" in tids or "AML.T0043" in tids


def test_no_ai_context_for_generic_cve():
    has_ai, tids = analyze_cve_ai_context(
        {
            "description": "Buffer overflow in nginx.",
            "affected_products": ["cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*"],
        }
    )
    assert has_ai is False
    assert tids == []


def test_infer_injection_hints():
    tids = infer_atlas_technique_ids(
        {"description": "SQL injection in model API endpoint.", "affected_products": []}
    )
    assert "AML.T0051" in tids


def test_cve_matches_declared_frameworks():
    cve = {
        "description": "Issue in PyTorch distributed training.",
        "affected_products": [],
        "has_ai_context": True,
    }
    assert cve_matches_declared_frameworks(cve, ["pytorch"]) is True
    assert cve_matches_declared_frameworks(cve, ["nginx"]) is False
