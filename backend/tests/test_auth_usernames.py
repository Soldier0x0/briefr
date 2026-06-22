"""Tests for auth/usernames.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from auth.usernames import normalize_username, validate_username


def test_validate_username_accepts_simple_name():
    assert validate_username("Ops") == "ops"


def test_validate_username_accepts_underscores_and_hyphens():
    assert validate_username("sec_ops-1") == "sec_ops-1"


def test_validate_username_rejects_too_short():
    with pytest.raises(ValueError):
        validate_username("ab")


def test_validate_username_rejects_invalid_characters():
    with pytest.raises(ValueError):
        validate_username("ops@home")


def test_validate_username_rejects_leading_hyphen():
    with pytest.raises(ValueError):
        validate_username("-ops")


def test_normalize_username_strips_and_lowercases():
    assert normalize_username("  Admin  ") == "admin"
