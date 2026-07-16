"""Shared Groq API settings for all BRIEFR LLM call sites."""

from __future__ import annotations

import os
from dataclasses import dataclass

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq replacement for deprecated llama-3.1-8b-instant (see console.groq.com/docs/deprecations).
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
GROQ_MODEL_SUMMARY = (
    os.environ.get("GROQ_MODEL_SUMMARY", "openai/gpt-oss-120b").strip()
    or "openai/gpt-oss-120b"
)


def scheduler_llm_timeout() -> float:
    """Per-provider HTTP timeout for scheduler-side LLM jobs (fail over faster)."""
    try:
        return max(10.0, float(os.environ.get("SCHEDULER_LLM_TIMEOUT_SECONDS", "30")))
    except ValueError:
        return 30.0


@dataclass(frozen=True)
class GroqLimits:
    rpm: int
    tpm: int
    estimated_tokens_per_request: int
    headroom_pct: int
    min_interval_seconds: float


def groq_limits() -> GroqLimits:
    """Limits for the configured model — override via env for other tiers/models."""
    from ai.llm_pacing import limits_from_env

    limits = limits_from_env(
        "GROQ",
        default_rpm=30,
        default_tpm=8000,
        default_est_tokens=1000,
        floor_seconds=0.5,
    )
    return GroqLimits(
        rpm=limits.rpm,
        tpm=limits.tpm,
        estimated_tokens_per_request=limits.estimated_tokens_per_request,
        headroom_pct=limits.headroom_pct,
        min_interval_seconds=limits.min_interval_seconds,
    )
