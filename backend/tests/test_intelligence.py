"""Tests for intelligence patch sentences."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from templates.intelligence import patch_sentence


def test_patch_sentence_avoids_duplicate_apply():
    text = patch_sentence(True, "Apply updates per vendor instructions")
    assert "Apply Apply" not in text
    assert "Apply updates per vendor instructions" in text
