"""Tests for wallboard session cookies."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wallboard.session import issue_session_token, verify_session_token


def test_issue_and_verify_session_token():
    token = issue_session_token()
    assert verify_session_token(token) is True


def test_verify_session_token_rejects_tamper():
    token = issue_session_token()
    assert verify_session_token(token + "x") is False


@pytest.mark.asyncio
async def test_wallboard_token_matches(monkeypatch):
    monkeypatch.setattr("wallboard.session.settings.wallboard_token", "secret-token-12345")
    monkeypatch.setattr("wallboard.session.settings.wallboard_auto_token", False)
    from wallboard.session import wallboard_token_matches

    assert await wallboard_token_matches("secret-token-12345") is True
    assert await wallboard_token_matches("wrong") is False
