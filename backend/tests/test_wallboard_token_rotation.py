"""Tests for wallboard auto-token rotation and issuance (issue #843)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wallboard.session import issue_session_token, verify_session_token
from wallboard.token_store import (
    issue_issuance_token,
    revoke_wallboard_tokens,
    rotate_wallboard_token,
    verify_issuance_token,
)


@pytest.mark.asyncio
async def test_rotate_and_issue_wallboard_token(monkeypatch, tmp_path):
    db_path = tmp_path / "wb-rotate.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    from settings import settings as app_settings

    monkeypatch.setattr(app_settings, "database_url", "")
    monkeypatch.setattr(app_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(app_settings, "db_path", str(db_path))
    monkeypatch.setattr(app_settings, "wallboard_auto_token", True)
    monkeypatch.setattr(app_settings, "wallboard_token", "seed-token")
    monkeypatch.setattr(app_settings, "jwt_secret", "test-jwt-secret")
    monkeypatch.setattr(app_settings, "wallboard_issuance_token_minutes", 5)

    from database import init_db

    await init_db()

    result = await rotate_wallboard_token(actor="pytest")
    assert result["generation"] >= 1

    token, _exp = issue_issuance_token(username="pytest", generation=result["generation"])
    assert verify_issuance_token(token, expected_generation=result["generation"]) is True
    assert verify_issuance_token(token, expected_generation=result["generation"] + 1) is False

    session = issue_session_token(generation=result["generation"])
    assert verify_session_token(session, expected_generation=result["generation"]) is True

    revoked = await revoke_wallboard_tokens(actor="pytest")
    assert revoked["generation"] > result["generation"]
    assert verify_issuance_token(token, expected_generation=revoked["generation"]) is False
    assert verify_session_token(session, expected_generation=revoked["generation"]) is False


def test_issue_and_verify_session_token_with_generation():
    token = issue_session_token(generation=2)
    assert verify_session_token(token, expected_generation=2) is True
    assert verify_session_token(token, expected_generation=3) is False


def test_legacy_session_rejected_when_generation_required():
    token = issue_session_token()
    assert verify_session_token(token, expected_generation=0) is True
    assert verify_session_token(token, expected_generation=1) is False
