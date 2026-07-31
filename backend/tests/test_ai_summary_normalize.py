"""Unit tests for executive summary normalization (PDF export path)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.summary import _normalize_result, _unwrap_nested_summary_field


def test_unwrap_nested_summary_field_extracts_inner_text():
    nested = (
        '{"executive_summary": "The investigation centers on CVE-2024-1234.", '
        '"key_findings": ["KEV listed"], "confidence": "high"}'
    )
    text, payload = _unwrap_nested_summary_field(nested)
    assert text == "The investigation centers on CVE-2024-1234."
    assert payload is not None
    assert payload["confidence"] == "high"


def test_unwrap_nested_summary_field_leaves_plain_text():
    text, payload = _unwrap_nested_summary_field("Plain analyst paragraph.")
    assert text == "Plain analyst paragraph."
    assert payload is None


def test_normalize_result_unwraps_nested_executive_summary_string():
    raw = {
        "executive_summary": (
            '{"executive_summary": "CVE-2024-9999 is critical and actively exploited.", '
            '"key_findings": ["Listed on CISA KEV"], "confidence": "high"}'
        ),
        "key_findings": ["Top-level finding kept when present"],
        "confidence": "medium",
    }
    cves = [{"cve_id": "CVE-2024-9999", "severity": "CRITICAL", "is_kev": True}]

    result = _normalize_result(raw, "groq", cves, [], [])

    assert result["executive_summary"] == "CVE-2024-9999 is critical and actively exploited."
    assert result["key_findings"] == ["Top-level finding kept when present"]
    assert result["confidence"] == "medium"
    assert result["source"] == "groq"


def test_normalize_result_uses_nested_findings_when_top_level_empty():
    raw = {
        "executive_summary": (
            '{"executive_summary": "Summary text.", '
            '"key_findings": ["Nested finding"], "confidence": "low"}'
        ),
        "key_findings": [],
    }

    result = _normalize_result(raw, "gemini", [], [], [])

    assert result["executive_summary"] == "Summary text."
    assert result["key_findings"] == ["Nested finding"]
    assert result["confidence"] == "low"
