"""Parse real-shaped OTX CVE indicator fixtures (golden tests)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from feeds.otx import _normalize_pulse

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "otx_cve_44228_general.json"


def test_otx_cve_fixture_parses_all_pulses():
    data = json.loads(FIXTURE.read_text())
    raw_pulses = data["pulse_info"]["pulses"]
    assert data["pulse_info"]["count"] == len(raw_pulses)

    pulses = [_normalize_pulse(p) for p in raw_pulses]
    assert len(pulses) == 2
    assert pulses[0]["author"] == "otx_analyst"
    assert pulses[0]["pulse_name"] == "Log4j Campaign Sample"
    assert pulses[1]["author"] == "legacy_string_author"
    assert all(isinstance(p["malware_families"], list) for p in pulses)
    assert all(isinstance(p["author"], str) for p in pulses)
