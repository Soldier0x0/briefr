"""Groq API client with RPM/TPM pacing from response headers.

Groq org limits are multi-dimensional (RPM, RPD, TPM, TPD) — you hit
whichever threshold is reached first. For ``llama-3.1-8b-instant`` the TPM
cap (6K/min) is usually tighter than RPM (30/min) for our extraction prompts.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

from ai.groq_config import GROQ_MODEL, GROQ_URL, groq_limits
from resilient_client import resilient_request

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_pause_until = 0.0
_last_request_at = 0.0


class GroqRateLimitError(Exception):
    """Groq returned HTTP 429 or headers indicate quota is exhausted."""


def _parse_duration_seconds(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    if text.isdigit():
        return float(text)
    match = re.match(r"^(?:(?P<mins>\d+)m)?(?:(?P<secs>\d+(?:\.\d+)?)s)?$", text)
    if not match:
        return 0.0
    mins = int(match.group("mins") or 0)
    secs = float(match.group("secs") or 0)
    return mins * 60.0 + secs


def _schedule_pause(seconds: float) -> None:
    global _pause_until
    if seconds <= 0:
        return
    _pause_until = max(_pause_until, time.monotonic() + seconds)


def _apply_rate_limit_headers(headers: httpx.Headers, *, estimated_tokens: int) -> None:
    retry_after = headers.get("retry-after")
    if retry_after:
        _schedule_pause(_parse_duration_seconds(retry_after))

    remaining_tokens = headers.get("x-ratelimit-remaining-tokens")
    reset_tokens = headers.get("x-ratelimit-reset-tokens")
    if remaining_tokens is not None and reset_tokens:
        try:
            if int(remaining_tokens) < estimated_tokens:
                _schedule_pause(_parse_duration_seconds(reset_tokens))
        except ValueError:
            pass

    remaining_requests = headers.get("x-ratelimit-remaining-requests")
    reset_requests = headers.get("x-ratelimit-reset-requests")
    if remaining_requests is not None and reset_requests:
        try:
            if int(remaining_requests) <= 0:
                _schedule_pause(_parse_duration_seconds(reset_requests))
        except ValueError:
            pass


def reset_groq_limiter_state() -> None:
    """Test helper — clear in-memory pacing state."""
    global _pause_until, _last_request_at
    _pause_until = 0.0
    _last_request_at = 0.0


async def await_groq_slot() -> None:
    """Wait until Groq header pacing and minimum inter-request interval allow a call."""
    global _last_request_at
    limits = groq_limits()
    async with _lock:
        now = time.monotonic()
        earliest = max(
            _pause_until,
            _last_request_at + limits.min_interval_seconds,
        )
        if earliest > now:
            wait = earliest - now
            logger.info("Groq pacing: sleeping %.1fs before next request", wait)
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()


async def chat_completion(
    api_key: str,
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 60.0,
    estimated_input_tokens: int | None = None,
    source: str = "groq",
) -> httpx.Response:
    """POST to Groq chat completions with quota-aware pacing."""
    limits = groq_limits()
    est_tokens = estimated_input_tokens
    if est_tokens is None:
        est_tokens = limits.estimated_tokens_per_request
    token_budget = est_tokens + max_tokens

    await await_groq_slot()
    try:
        response = await resilient_request(
            source,
            "POST",
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=timeout,
            retries=0,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            _apply_rate_limit_headers(exc.response.headers, estimated_tokens=token_budget)
            retry_after = exc.response.headers.get("retry-after", "")
            raise GroqRateLimitError(
                f"Groq rate limit (HTTP 429)"
                + (f", retry-after={retry_after}" if retry_after else "")
            ) from exc
        raise

    _apply_rate_limit_headers(response.headers, estimated_tokens=token_budget)
    return response


def message_content(response: httpx.Response) -> str:
    return (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        or ""
    )
