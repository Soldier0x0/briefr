"""Product voice regression tests for operational priority rationale."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.priority import _RATIONALE


def test_high_confirmed_rationale_does_not_question_environment_presence():
    text = _RATIONALE[("HIGH", "CONFIRMED")]
    assert "if product is in your environment" not in text.lower()
    assert "confirmed vulnerable version match" in text.lower()
    assert "investigate exposure" in text.lower()
