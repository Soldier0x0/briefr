"""Lightweight API key health pings for operator monitoring (Issue 21)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from database import get_sync_state_value, set_sync_state_value
from resilient_client import resilient_request

logger = logging.getLogger(__name__)

API_KEY_HEALTH_PREFIX = "api_key_health:"

CheckFn = Callable[[str], Awaitable[dict[str, Any]]]

_DIGITS_RE = re.compile(r"\d+")


def _normalize_for_dedupe(error_text: str) -> str:
    """Collapse digit runs so dedupe keys stay stable across occurrences of
    the *same kind* of failure even when the message embeds a value that
    changes every time (Unix timestamps, ports, byte counts, retry-after
    seconds). Only used for the dedupe key — the raw error_text is still
    shown to the operator unmodified."""
    return _DIGITS_RE.sub("#", error_text)


def _placeholder_key(value: str) -> bool:
    raw = (value or "").strip()
    return not raw or raw.lower().startswith("your_")


def _suffix(value: str) -> str | None:
    raw = (value or "").strip()
    if _placeholder_key(raw) or len(raw) < 8:
        return None
    return f"{raw[:4]}…{raw[-4:]}"


async def _ping_json(
    *,
    source: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    ok_statuses: frozenset[int] = frozenset({200}),
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = await resilient_request(
            source,
            method,
            url,
            queue_operation="api_key_health",
            headers=headers or {},
            params=params,
            timeout=20.0,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        healthy = response.status_code in ok_statuses
        return {
            "healthy": healthy,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": None if healthy else f"HTTP {response.status_code}",
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "healthy": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "error": f"{type(exc).__name__}: {exc}"[:240],
        }


async def _check_nvd(api_key: str) -> dict[str, Any]:
    headers = {"apiKey": api_key} if api_key else {}
    return await _ping_json(
        source="nvd",
        method="GET",
        url="https://services.nvd.nist.gov/rest/json/cves/2.0",
        headers=headers,
        params={"resultsPerPage": "1"},
        ok_statuses=frozenset({200, 403}),
    )


async def _check_groq(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="groq",
        method="GET",
        url="https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )


async def _check_gemini(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="gemini",
        method="GET",
        url="https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key},
    )


async def _check_cerebras(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="cerebras",
        method="GET",
        url="https://api.cerebras.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )


async def _check_openrouter(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="openrouter",
        method="GET",
        url="https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )


async def _check_virustotal(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="virustotal",
        method="GET",
        url="https://www.virustotal.com/api/v3/domains/google.com",
        headers={"x-apikey": api_key},
        ok_statuses=frozenset({200, 404}),
    )


async def _check_github(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="github",
        method="GET",
        url="https://api.github.com/rate_limit",
        headers={"Authorization": f"Bearer {api_key}"},
    )


async def _check_otx(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="otx",
        method="GET",
        url="https://otx.alienvault.com/api/v1/pulses/subscribed",
        headers={"X-OTX-API-KEY": api_key},
        params={"limit": "1"},
    )


async def _check_greynoise(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="greynoise",
        method="GET",
        url="https://api.greynoise.io/v3/community/8.8.8.8",
        headers={"key": api_key},
        ok_statuses=frozenset({200, 404}),
    )


async def _check_abuseipdb(api_key: str) -> dict[str, Any]:
    return await _ping_json(
        source="abuseipdb",
        method="GET",
        url="https://api.abuseipdb.com/api/v2/check",
        headers={"Key": api_key, "Accept": "application/json"},
        params={"ipAddress": "8.8.8.8", "maxAgeInDays": "90"},
    )


PROVIDER_CHECKS: list[dict[str, Any]] = [
    {"provider": "nvd", "env_key": "NVD_API_KEY", "optional": True, "check": _check_nvd},
    {"provider": "groq", "env_key": "GROQ_API_KEY", "optional": True, "check": _check_groq},
    {"provider": "gemini", "env_key": "GEMINI_API_KEY", "optional": True, "check": _check_gemini},
    {"provider": "cerebras", "env_key": "CEREBRAS_API_KEY", "optional": True, "check": _check_cerebras},
    {"provider": "openrouter", "env_key": "OPENROUTER_API_KEY", "optional": True, "check": _check_openrouter},
    {"provider": "virustotal", "env_key": "VIRUSTOTAL_API_KEY", "optional": True, "check": _check_virustotal},
    {"provider": "github", "env_key": "GITHUB_TOKEN", "optional": True, "check": _check_github},
    {"provider": "otx", "env_key": "OTX_API_KEY", "optional": True, "check": _check_otx},
    {"provider": "greynoise", "env_key": "GREYNOISE_API_KEY", "optional": True, "check": _check_greynoise},
    {"provider": "abuseipdb", "env_key": "ABUSEIPDB_API_KEY", "optional": True, "check": _check_abuseipdb},
]


def _state_key(provider: str) -> str:
    return f"{API_KEY_HEALTH_PREFIX}{provider}"


async def load_api_key_health_row(db, provider: str) -> dict[str, Any] | None:
    raw = await get_sync_state_value(db, _state_key(provider))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def build_api_key_health_payload(db) -> dict[str, Any]:
    providers: list[dict[str, Any]] = []
    for spec in PROVIDER_CHECKS:
        env_key = spec["env_key"]
        provider = spec["provider"]
        raw_key = os.environ.get(env_key, "")
        configured = not _placeholder_key(raw_key)
        stored = await load_api_key_health_row(db, provider)
        row: dict[str, Any] = {
            "provider": provider,
            "env_key": env_key,
            "configured": configured,
            "key_suffix": _suffix(raw_key) if configured else None,
            "healthy": None,
            "last_checked_at": None,
            "latency_ms": None,
            "status_code": None,
            "error": None,
        }
        if stored:
            row.update(
                {
                    "healthy": stored.get("healthy"),
                    "last_checked_at": stored.get("checked_at"),
                    "latency_ms": stored.get("latency_ms"),
                    "status_code": stored.get("status_code"),
                    "error": stored.get("error"),
                }
            )
        providers.append(row)

    configured_count = sum(1 for row in providers if row["configured"])
    healthy_count = sum(
        1 for row in providers if row["configured"] and row.get("healthy") is True
    )
    return {
        "providers": providers,
        "configured_count": configured_count,
        "healthy_count": healthy_count,
        "checked_at": max(
            (row["last_checked_at"] for row in providers if row.get("last_checked_at")),
            default=None,
        ),
    }


async def run_api_key_health_checks(db) -> dict[str, int]:
    """Ping configured providers and persist results in sync_state."""
    checked = 0
    healthy = 0
    for spec in PROVIDER_CHECKS:
        provider = spec["provider"]
        env_key = spec["env_key"]
        raw_key = os.environ.get(env_key, "").strip()
        if _placeholder_key(raw_key):
            continue
        result = await spec["check"](raw_key)
        checked += 1
        if result.get("healthy"):
            healthy += 1
        payload = {
            "provider": provider,
            "healthy": bool(result.get("healthy")),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latency_ms": result.get("latency_ms"),
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        }
        await set_sync_state_value(db, _state_key(provider), json.dumps(payload))
        if not payload["healthy"]:
            logger.warning(
                "API key health check failed for %s: %s",
                provider,
                payload["error"] or f"HTTP {payload.get('status_code')}",
                extra={"provider": provider, "monitor": "api_key_health"},
            )
            try:
                from notifications.emit import emit_api_key_unhealthy_notification

                error_text = str(payload.get("error") or f"HTTP {payload.get('status_code')}")
                await emit_api_key_unhealthy_notification(
                    db,
                    provider=provider,
                    error=error_text,
                    # Stable per (provider, error) — not per run — so a
                    # provider stuck on the same failure notifies once, not
                    # every 6h. A *different* error still gets its own
                    # notification (real signal: something changed).
                    # error_text is normalized (not used raw) because some
                    # exception messages embed dynamic values that would
                    # otherwise defeat this exact stability guarantee — e.g.
                    # CircuitOpenError's "retry after <unix-ts>"
                    # (resilient_client.py) changes every occurrence.
                    dedupe_key=f"api_key:{provider}:{_normalize_for_dedupe(error_text)}",
                )
            except Exception as exc:
                logger.warning(
                    "Failed to emit API key unhealthy notification for %s: %s",
                    provider,
                    exc,
                )
    await db.commit()
    return {"checked": checked, "healthy": healthy}
