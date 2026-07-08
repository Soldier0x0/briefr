"""Tests for intelligence patch sentences."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from templates.intelligence import kev_sentence, patch_sentence


def test_patch_sentence_avoids_duplicate_apply():
    text = patch_sentence(True, "Apply updates per vendor instructions")
    assert "Apply Apply" not in text
    assert "Apply updates per vendor instructions" in text


def test_kev_status_sentence_is_not_remediation_action():
    """sentences.kev is catalogue status — required_action is separate."""
    status = kev_sentence(True, "2026-02-01")
    required_action = "Apply vendor patch immediately."
    assert "catalogue" in status.lower() or "CISA" in status
    assert required_action not in status


def test_patch_sentence_without_patch_ignores_required_action():
    """When patch_available is false, patch sentence stays generic (UI uses kev_required_action)."""
    fix = "Apply vendor patch immediately."
    text = patch_sentence(False, fix)
    assert fix not in text
    assert "No official patch" in text
