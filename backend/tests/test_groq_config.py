"""Groq model defaults for all LLM call sites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.groq_config import GROQ_MODEL, GROQ_MODEL_SUMMARY


def test_groq_model_is_gpt_oss_20b():
    assert GROQ_MODEL == "openai/gpt-oss-20b"


def test_groq_summary_model_is_gpt_oss_120b():
    assert GROQ_MODEL_SUMMARY == "openai/gpt-oss-120b"
