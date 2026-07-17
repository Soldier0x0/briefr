"""Google Gemini generateContent client."""

from __future__ import annotations

import os

from api_queue import apply_rate_limit_headers
from ai.llm_payload import has_llm_request_payload
from resilient_client import resilient_request

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def gemini_model() -> str:
    # gemini-2.0-flash-lite is deprecated on Google AI; prefer current Flash-Lite.
    return (
        os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
        or "gemini-2.5-flash-lite"
    )


def _messages_to_gemini(messages: list[dict[str, str]]) -> tuple[str, list[dict]]:
    system_parts: list[str] = []
    contents: list[dict] = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})
    system_instruction = "\n\n".join(system_parts)
    return system_instruction, contents


async def gemini_chat_completion(
    api_key: str,
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 60.0,
    queue_operation: str | None = None,
    queue_context_type: str | None = None,
    queue_context_id: str | None = None,
    usage_out: dict | None = None,
) -> str:
    if not has_llm_request_payload(messages):
        return ""

    model_name = model or gemini_model()
    system_instruction, contents = _messages_to_gemini(messages)
    if not contents:
        return ""

    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"{GEMINI_BASE}/{model_name}:generateContent"
    response = await resilient_request(
        "gemini",
        "POST",
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=timeout,
        retries=0,
        wait_on_rate_limit=True,
        wait_on_circuit=True,
        queue_operation=queue_operation,
        queue_context_type=queue_context_type,
        queue_context_id=queue_context_id,
    )
    apply_rate_limit_headers("gemini", response.headers, estimated_tokens=max_tokens + 500)
    try:
        data = response.json()
        if usage_out is not None and isinstance(data.get("usageMetadata"), dict):
            m = data["usageMetadata"]
            usage_out["input_tokens"] = m.get("promptTokenCount")
            usage_out["output_tokens"] = m.get("candidatesTokenCount")
            usage_out["total_tokens"] = m.get("totalTokenCount")
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts") or []
            return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        pass
    return ""
