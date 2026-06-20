"""Groq model is pinned for all LLM call sites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.groq_config import GROQ_MODEL


def test_groq_model_is_llama_31_8b_instant():
    assert GROQ_MODEL == "llama-3.1-8b-instant"
