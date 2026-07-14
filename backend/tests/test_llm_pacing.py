"""LLM provider pacing — RPM/TPM headroom intervals."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.groq_config import groq_limits
from ai.llm_pacing import (
    cerebras_limits,
    compute_min_interval,
    gemini_limits,
    limits_from_env,
    openrouter_limits,
)
from source_rate_limits import get_source_pacing


def test_compute_min_interval_uses_headroom():
    # 30 RPM @ 85% headroom => effective 25.5 RPM => ~2.35s from RPM alone,
    # but 8K TPM @ 85% with 1500 est tokens => ~13.2s — TPM wins.
    interval = compute_min_interval(
        rpm=30,
        tpm=8000,
        estimated_tokens=1500,
        headroom_pct=85,
        floor_seconds=0.5,
    )
    assert interval >= 13.0
    assert interval < 14.0


def test_gemini_defaults_conservative():
    limits = gemini_limits()
    assert limits.rpm == 15
    assert limits.tpm == 250_000
    assert limits.min_interval_seconds >= 0.5


def test_cerebras_defaults_conservative():
    limits = cerebras_limits()
    assert limits.rpm == 5
    assert limits.tpm == 30_000
    assert limits.min_interval_seconds >= 0.5


def test_openrouter_defaults_conservative():
    limits = openrouter_limits()
    assert limits.rpm == 20
    assert limits.tpm == 40_000
    assert limits.min_interval_seconds >= 1.0


def test_groq_limits_use_headroom(monkeypatch):
    monkeypatch.delenv("GROQ_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    monkeypatch.setenv("GROQ_RPM_LIMIT", "30")
    monkeypatch.setenv("GROQ_TPM_LIMIT", "8000")
    monkeypatch.setenv("GROQ_HEADROOM_PCT", "85")
    limits = groq_limits()
    assert limits.headroom_pct == 85
    assert limits.min_interval_seconds >= 13.0


def test_source_rate_limits_wires_llm_providers(monkeypatch):
    monkeypatch.delenv("GEMINI_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("CEREBRAS_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS", raising=False)
    gemini = get_source_pacing("gemini")
    cerebras = get_source_pacing("cerebras")
    openrouter = get_source_pacing("openrouter")
    groq = get_source_pacing("groq")
    assert gemini.min_interval_seconds >= 0.5
    assert cerebras.min_interval_seconds >= 0.5
    assert openrouter.min_interval_seconds >= 1.0
    assert groq.min_interval_seconds >= 0.5


def test_env_override_min_interval(monkeypatch):
    monkeypatch.setenv("GEMINI_RPM_LIMIT", "15")
    monkeypatch.setenv("GEMINI_TPM_LIMIT", "250000")
    monkeypatch.setenv("GEMINI_MIN_REQUEST_INTERVAL_SECONDS", "5")
    limits = limits_from_env(
        "GEMINI",
        default_rpm=15,
        default_tpm=250_000,
    )
    assert limits.min_interval_seconds == 5.0
