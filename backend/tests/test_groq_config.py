"""Groq model defaults for all LLM call sites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.groq_config import GROQ_MODEL, GROQ_MODEL_SUMMARY, scheduler_llm_timeout


def test_groq_model_is_gpt_oss_20b():
    assert GROQ_MODEL == "openai/gpt-oss-20b"


def test_groq_summary_model_is_gpt_oss_120b():
    assert GROQ_MODEL_SUMMARY == "openai/gpt-oss-120b"


def test_scheduler_llm_timeout_default():
    assert scheduler_llm_timeout() == 30.0


def test_groq_defaults_avoid_deprecated_llama(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_MODEL_SUMMARY", raising=False)
    import importlib

    import ai.groq_config as gc

    importlib.reload(gc)
    assert "llama" not in gc.GROQ_MODEL.lower()
    assert "llama" not in gc.GROQ_MODEL_SUMMARY.lower()
