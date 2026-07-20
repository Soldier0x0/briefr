"""F1.10: correlation narrative helpers live in correlation.narrative (not copy)."""

from correlation.narrative import (
    __doc__ as narrative_doc,
    campaign_summary,
    infrastructure_summary,
    sanitize_pulse_text,
)


def test_narrative_module_importable():
    assert narrative_doc
    assert callable(sanitize_pulse_text)
    assert callable(infrastructure_summary)
    assert callable(campaign_summary)
    assert "Shares" in infrastructure_summary("CVE-2024-1", {"HASH": 1})
