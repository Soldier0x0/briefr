"""Custom override resolution for outbound pacing."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from source_rate_limits import get_source_pacing


def test_resolve_pacing_key_aliases(monkeypatch):
    monkeypatch.setenv("OUTBOUND_PACING_TIER", "custom")
    monkeypatch.setenv("OUTBOUND_PACING_OVERRIDES", json.dumps({"github": 0.1}))
    assert get_source_pacing("poc_github").min_interval_seconds == 0.1


def test_free_tier_ignores_custom_json(monkeypatch):
    monkeypatch.setenv("OUTBOUND_PACING_TIER", "free")
    monkeypatch.setenv("OUTBOUND_PACING_OVERRIDES", json.dumps({"otx": 99.0}))
    assert get_source_pacing("otx").min_interval_seconds < 99.0
