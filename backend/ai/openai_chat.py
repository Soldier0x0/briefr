"""OpenAI-compatible chat completion helper (Groq, Cerebras, OpenRouter)."""

from __future__ import annotations

from api_queue import apply_rate_limit_headers
from resilient_client import resilient_request


async def openai_chat_completion(
    *,
    source: str,
    url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 60.0,
    extra_headers: dict[str, str] | None = None,
    queue_operation: str | None = None,
    queue_context_type: str | None = None,
    queue_context_id: str | None = None,
    usage_out: dict | None = None,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    response = await resilient_request(
        source,
        "POST",
        url,
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=timeout,
        retries=0,
        wait_on_rate_limit=True,
        wait_on_circuit=True,
        queue_operation=queue_operation,
        queue_context_type=queue_context_type,
        queue_context_id=queue_context_id,
    )
    apply_rate_limit_headers(source, response.headers, estimated_tokens=max_tokens + 500)
    try:
        data = response.json()
        if isinstance(data, dict):
            if usage_out is not None and isinstance(data.get("usage"), dict):
                u = data["usage"]
                usage_out["input_tokens"] = u.get("prompt_tokens")
                usage_out["output_tokens"] = u.get("completion_tokens")
                usage_out["total_tokens"] = u.get("total_tokens")
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                or ""
            )
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        pass
    return ""
