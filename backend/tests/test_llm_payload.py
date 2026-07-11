"""Tests for outbound LLM payload validation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.llm_payload import (
    has_llm_request_payload,
    has_substantive_source_text,
    user_message_text,
)


def test_user_message_text_concatenates_user_and_assistant():
    messages = [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "prior"},
    ]
    assert user_message_text(messages) == "hello\nprior"


def test_has_llm_request_payload_false_for_system_only():
    assert has_llm_request_payload([{"role": "system", "content": "only system"}]) is False


def test_has_llm_request_payload_false_for_whitespace_user():
    assert has_llm_request_payload([{"role": "user", "content": "   \n"}]) is False


def test_has_llm_request_payload_true_for_user_content():
    assert has_llm_request_payload([{"role": "user", "content": "data"}]) is True


def test_has_substantive_source_text_requires_min_chars():
    assert has_substantive_source_text("") is False
    assert has_substantive_source_text("short") is False
    assert has_substantive_source_text("x" * 8) is True
