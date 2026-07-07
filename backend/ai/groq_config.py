"""Shared Groq API settings for all BRIEFR LLM call sites."""

from __future__ import annotations

import os
from dataclasses import dataclass

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
GROQ_MODEL_SUMMARY = (
    os.environ.get("GROQ_MODEL_SUMMARY", "openai/gpt-oss-120b").strip()
    or "openai/gpt-oss-120b"
)


@dataclass(frozen=True)
class GroqLimits:
    rpm: int
    tpm: int
    estimated_tokens_per_request: int
    min_interval_seconds: float


def groq_limits() -> GroqLimits:
    """Limits for the configured model — override via env for other tiers/models."""
    try:
        rpm = int(os.environ.get("GROQ_RPM_LIMIT", "30"))
    except ValueError:
        rpm = 30
    try:
        tpm = int(os.environ.get("GROQ_TPM_LIMIT", "6000"))
    except ValueError:
        tpm = 6000
    try:
        est_tokens = int(os.environ.get("GROQ_ESTIMATED_TOKENS_PER_REQUEST", "1500"))
    except ValueError:
        est_tokens = 1500

    min_from_rpm = 60.0 / max(rpm, 1)
    min_from_tpm = (60.0 * est_tokens) / max(tpm, 1)
    default_interval = max(min_from_rpm, min_from_tpm, 2.0)

    try:
        interval = float(
            os.environ.get("GROQ_MIN_REQUEST_INTERVAL_SECONDS", str(default_interval))
        )
    except ValueError:
        interval = default_interval

    return GroqLimits(
        rpm=rpm,
        tpm=tpm,
        estimated_tokens_per_request=est_tokens,
        min_interval_seconds=max(interval, 0.5),
    )
