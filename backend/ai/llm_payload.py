"""Outbound LLM request payload validation — skip API calls when there is nothing to send."""

from __future__ import annotations

import os

# Minimum non-whitespace chars in user/assistant messages before any provider is called.
_DEFAULT_MIN_USER_CHARS = 1


def _min_user_chars() -> int:
    raw = os.environ.get("LLM_MIN_USER_CHARS", "").strip()
    if not raw:
        return _DEFAULT_MIN_USER_CHARS
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MIN_USER_CHARS


def user_message_text(messages: list[dict[str, str]] | None) -> str:
    """Concatenate user and assistant message bodies (the outbound prompt payload)."""
    if not messages:
        return ""
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or "").lower()
        if role not in {"user", "assistant"}:
            continue
        text = (msg.get("content") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def has_llm_request_payload(
    messages: list[dict[str, str]] | None,
    *,
    min_user_chars: int | None = None,
) -> bool:
    """True when at least one user/assistant message has enough content to justify a call."""
    floor = _min_user_chars() if min_user_chars is None else max(1, min_user_chars)
    return len(user_message_text(messages)) >= floor


def has_substantive_source_text(text: str | None, *, min_chars: int = 8) -> bool:
    """True when caller-supplied source text (CVE description, exploit text, etc.) is non-trivial."""
    return len((text or "").strip()) >= max(1, min_chars)
