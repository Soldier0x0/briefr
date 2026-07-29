"""Outbound pacing tier presets and custom overrides."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from source_rate_limits import get_source_pacing, pacing_defaults_payload, resolve_pacing_tier


def test_resolve_pacing_tier_defaults_free(monkeypatch):
    monkeypatch.delenv("OUTBOUND_PACING_TIER", raising=False)
    assert resolve_pacing_tier() == "free"


def test_custom_override_interval(monkeypatch):
    monkeypatch.setenv("OUTBOUND_PACING_TIER", "custom")
    monkeypatch.setenv("OUTBOUND_PACING_OVERRIDES", json.dumps({"nvd": 12.0}))
    assert get_source_pacing("nvd").min_interval_seconds == 12.0


def test_premium_auto_relaxes_when_key_present(monkeypatch):
    monkeypatch.setenv("OUTBOUND_PACING_TIER", "premium_auto")
    monkeypatch.setenv("NVD_API_KEY", "test-key")
    premium = get_source_pacing("nvd").min_interval_seconds
    monkeypatch.setenv("OUTBOUND_PACING_TIER", "free")
    monkeypatch.delenv("NVD_API_KEY", raising=False)
    free = get_source_pacing("nvd").min_interval_seconds
    assert premium < free


def test_pacing_defaults_payload_includes_sources():
    payload = pacing_defaults_payload()
    assert "nvd" in payload["sources"]
