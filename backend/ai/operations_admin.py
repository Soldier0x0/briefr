"""Admin payloads for AI Operations (AI-2)."""

from __future__ import annotations

import os
from typing import Any

from ai.llm_router import any_llm_provider_configured, get_configured_providers
from ai.model_catalog import PROVIDER_ENV_KEYS, models_catalog_payload
from ai.operations_recorder import recording_enabled
from resilient_client import get_feed_health


def _env_flag(key: str, default: str = "0") -> bool:
    return os.environ.get(key, default).strip().lower() in ("1", "true", "yes", "on")


def _provider_health_rows() -> list[dict[str, Any]]:
    feed = get_feed_health()
    configured = set(get_configured_providers())
    rows: list[dict[str, Any]] = []
    for provider, env_key in PROVIDER_ENV_KEYS.items():
        health = feed.get(provider, {})
        rows.append(
            {
                "provider": provider,
                "env_key": env_key,
                "configured": provider in configured,
                "circuit_open": bool(health.get("circuit_open")),
                "last_success": health.get("last_success"),
                "last_failure": health.get("last_failure"),
                "last_error": health.get("last_error"),
                "consecutive_failures": int(health.get("consecutive_failures") or 0),
            }
        )
    return rows


def build_overview_payload(
    *,
    usage_24h: dict[str, Any],
    usage_7d: dict[str, Any],
    total_operations: int,
    embeddings_vector_count: int,
) -> dict[str, Any]:
    providers = _provider_health_rows()
    active_circuits = sum(1 for p in providers if p["circuit_open"])
    configured_count = sum(1 for p in providers if p["configured"])
    llm_available = any_llm_provider_configured()

    return {
        "recording_enabled": recording_enabled(),
        "any_provider_configured": llm_available,
        "configured_provider_count": configured_count,
        "active_circuit_count": active_circuits,
        "usage": {
            "24h": usage_24h,
            "7d": usage_7d,
        },
        "total_operations": total_operations,
        "features": {
            "pdf_summary": {
                "label": "PDF executive summary",
                "trigger": "on_demand",
                "available": llm_available,
            },
            "product_extraction": {
                "label": "LLM product extraction",
                "trigger": "scheduler",
                "enabled": _env_flag("LLM_PRODUCT_EXTRACTION_ENABLED"),
                "available": llm_available,
            },
            "detection_context_llm": {
                "label": "Detection context LLM",
                "trigger": "scheduler",
                "enabled": _env_flag("DETECTION_CONTEXT_LLM_ENABLED"),
                "available": llm_available,
            },
            "embeddings": {
                "label": "CVE embeddings (local)",
                "trigger": "scheduler",
                "enabled": _env_flag("EMBEDDINGS_ENABLED"),
                "vector_count": embeddings_vector_count,
            },
        },
        "api_keys_path": "/admin?p=apikeys",
    }


def build_providers_payload() -> dict[str, Any]:
    return {
        "providers": _provider_health_rows(),
        "configured": get_configured_providers(),
    }


def build_models_payload() -> dict[str, Any]:
    return models_catalog_payload()
