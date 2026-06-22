"""Tests for auth/passwords.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.passwords import DUMMY_HASH, hash_password, verify_password


def test_hash_password_is_not_plaintext():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert hashed.startswith("$2b$")


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-real-hash") is False


def test_dummy_hash_never_verifies():
    assert verify_password("not-a-real-password", DUMMY_HASH) is True
    assert verify_password("something-else", DUMMY_HASH) is False
