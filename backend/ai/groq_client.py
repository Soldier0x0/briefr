"""Groq API client — uses global API queue via resilient_request."""

from __future__ import annotations

import httpx

from ai.groq_config import GROQ_MODEL, GROQ_URL, groq_limits
from api_queue import apply_rate_limit_headers, reset_api_queue
from resilient_client import resilient_request

GROQ_RATE_LIMIT_MAX_RETRIES = 50  # retained for tests that monkeypatch


class GroqRateLimitError(Exception):
    """Legacy — resilient_request now waits on 429 instead of raising."""


def reset_groq_limiter_state() -> None:
    """Test helper."""
    reset_api_queue()


async def await_groq_slot() -> None:
    """Compatibility shim — pacing is handled inside resilient_request."""
    return None


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
    """POST to Groq chat completions — waits in queue on rate limits, never drops."""
    limits = groq_limits()
    est_tokens = estimated_input_tokens or limits.estimated_tokens_per_request
    token_budget = est_tokens + max_tokens

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
        wait_on_rate_limit=True,
        wait_on_circuit=True,
    )
    apply_rate_limit_headers(
        source, response.headers, estimated_tokens=token_budget
    )
    return response


def message_content(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                or ""
            )
    except (ValueError, TypeError, KeyError, IndexError):
        pass
    return ""
