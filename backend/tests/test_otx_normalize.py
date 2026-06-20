"""Tests for OTX pulse normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.otx import _normalize_pulse


def test_normalize_pulse_author_dict():
    raw = {
        "id": "6231ee27e6834a707de700ae",
        "name": "Log4j Campaign",
        "created": "2022-03-16T14:03:19.241000",
        "author": {"username": "alice", "id": "123"},
        "tags": ["cve"],
    }
    pulse = _normalize_pulse(raw)
    assert pulse["author"] == "alice"
    assert pulse["pulse_id"] == "6231ee27e6834a707de700ae"
    assert pulse["pulse_name"] == "Log4j Campaign"


def test_normalize_pulse_malware_family_objects():
    raw = {
        "id": "abc",
        "name": "Test",
        "author": "x",
        "malware_families": [{"name": "Emotet"}, "trickbot"],
    }
    pulse = _normalize_pulse(raw)
    assert pulse["malware_families"] == ["Emotet", "trickbot"]
