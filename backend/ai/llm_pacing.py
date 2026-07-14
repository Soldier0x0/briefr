"""Shared LLM provider pacing — RPM/TPM headroom for outbound API queue spacing."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderLimits:
    rpm: int
    tpm: int
    estimated_tokens_per_request: int
    headroom_pct: int
    min_interval_seconds: float


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def compute_min_interval(
    *,
    rpm: int,
    tpm: int,
    estimated_tokens: int,
    headroom_pct: int,
    floor_seconds: float = 0.5,
    override_seconds: float | None = None,
) -> float:
    """Minimum spacing between requests using effective RPM/TPM after headroom."""
    effective_rpm = max(rpm * headroom_pct / 100.0, 1.0)
    effective_tpm = max(tpm * headroom_pct / 100.0, 1.0)
    min_from_rpm = 60.0 / effective_rpm
    min_from_tpm = (60.0 * estimated_tokens) / effective_tpm
    default_interval = max(min_from_rpm, min_from_tpm, floor_seconds)
    if override_seconds is not None:
        return max(override_seconds, floor_seconds)
    return max(default_interval, floor_seconds)


def limits_from_env(
    prefix: str,
    *,
    default_rpm: int,
    default_tpm: int,
    default_est_tokens: int = 1500,
    default_headroom_pct: int = 85,
    floor_seconds: float = 0.5,
    default_min_interval: float | None = None,
) -> ProviderLimits:
    rpm = _env_int(f"{prefix}_RPM_LIMIT", default_rpm)
    tpm = _env_int(f"{prefix}_TPM_LIMIT", default_tpm)
    est_tokens = _env_int(f"{prefix}_ESTIMATED_TOKENS_PER_REQUEST", default_est_tokens)
    headroom = _env_int(f"{prefix}_HEADROOM_PCT", default_headroom_pct)
    override_raw = os.environ.get(f"{prefix}_MIN_REQUEST_INTERVAL_SECONDS", "").strip()
    override = None
    if override_raw:
        override = _env_float(f"{prefix}_MIN_REQUEST_INTERVAL_SECONDS", 0.0)
    elif default_min_interval is not None:
        override = default_min_interval

    interval = compute_min_interval(
        rpm=rpm,
        tpm=tpm,
        estimated_tokens=est_tokens,
        headroom_pct=headroom,
        floor_seconds=floor_seconds,
        override_seconds=override,
    )
    return ProviderLimits(
        rpm=rpm,
        tpm=tpm,
        estimated_tokens_per_request=est_tokens,
        headroom_pct=headroom,
        min_interval_seconds=interval,
    )


def gemini_limits() -> ProviderLimits:
    """Gemini Flash-Lite free tier defaults (15 RPM, 250K TPM)."""
    return limits_from_env(
        "GEMINI",
        default_rpm=15,
        default_tpm=250_000,
        default_est_tokens=1500,
        floor_seconds=0.5,
    )


def cerebras_limits() -> ProviderLimits:
    """Cerebras free-trial defaults (5 RPM, 30K TPM per inference-docs)."""
    return limits_from_env(
        "CEREBRAS",
        default_rpm=5,
        default_tpm=30_000,
        default_est_tokens=1500,
        floor_seconds=0.5,
    )


def openrouter_limits() -> ProviderLimits:
    """OpenRouter :free tier defaults (20 RPM, 40K TPM)."""
    return limits_from_env(
        "OPENROUTER",
        default_rpm=20,
        default_tpm=40_000,
        default_est_tokens=1500,
        floor_seconds=1.0,
    )
