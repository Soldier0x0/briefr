"""Built-in LLM provider catalog + custom OpenAI-compatible slot (Phase E)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

MODEL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$")


@dataclass(frozen=True)
class ProviderCatalogEntry:
    id: str
    label: str
    base_url: str
    default_model: str
    env_key_field: str
    openai_compatible: bool = True
    notes: str = ""


BUILTIN_CATALOG: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1/chat/completions",
        default_model="deepseek-chat",
        env_key_field="DEEPSEEK_API_KEY",
    ),
    ProviderCatalogEntry(
        id="kimi",
        label="Kimi (Moonshot)",
        base_url="https://api.moonshot.cn/v1/chat/completions",
        default_model="moonshot-v1-8k",
        env_key_field="MOONSHOT_API_KEY",
    ),
    ProviderCatalogEntry(
        id="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1/chat/completions",
        default_model="gpt-4o-mini",
        env_key_field="OPENAI_API_KEY",
    ),
    ProviderCatalogEntry(
        id="anthropic",
        label="Anthropic",
        base_url="https://api.anthropic.com/v1/messages",
        default_model="claude-3-5-haiku-20241022",
        env_key_field="ANTHROPIC_API_KEY",
        openai_compatible=False,
        notes="Messages API — not wired to OpenAI chat router; catalog reference only.",
    ),
    ProviderCatalogEntry(
        id="google_gemini",
        label="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        default_model="gemini-3.1-flash-lite",
        env_key_field="GEMINI_API_KEY",
        notes="Scheduler uses native Gemini client when GEMINI_API_KEY is set.",
    ),
)

CUSTOM_ENV_KEYS = {
    "base_url": "CUSTOM_LLM_BASE_URL",
    "api_key": "CUSTOM_LLM_API_KEY",
    "model": "CUSTOM_LLM_MODEL",
}


def validate_model_name(model: str) -> bool:
    return bool(MODEL_NAME_RE.match((model or "").strip()))


def _is_usable(value: str) -> bool:
    val = (value or "").strip()
    if not val:
        return False
    lowered = val.lower()
    if lowered in ("your_key_here", "your_api_key_here", "your_key") or lowered.startswith("your_"):
        return False
    if "placeholder" in lowered:
        return False
    return True


def custom_provider_configured() -> bool:
    base = os.environ.get(CUSTOM_ENV_KEYS["base_url"], "").strip()
    key = os.environ.get(CUSTOM_ENV_KEYS["api_key"], "").strip()
    model = os.environ.get(CUSTOM_ENV_KEYS["model"], "").strip()
    return bool(base and _is_usable(key) and model and validate_model_name(model))


def custom_provider_step() -> tuple[str, str, str] | None:
    if not custom_provider_configured():
        return None
    return (
        os.environ.get(CUSTOM_ENV_KEYS["base_url"], "").strip().rstrip("/"),
        os.environ.get(CUSTOM_ENV_KEYS["api_key"], "").strip(),
        os.environ.get(CUSTOM_ENV_KEYS["model"], "").strip(),
    )


def catalog_status_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in BUILTIN_CATALOG:
        configured = _is_usable(os.environ.get(entry.env_key_field, ""))
        rows.append(
            {
                "id": entry.id,
                "label": entry.label,
                "base_url": entry.base_url,
                "default_model": entry.default_model,
                "env_key_field": entry.env_key_field,
                "openai_compatible": entry.openai_compatible,
                "configured": configured,
                "notes": entry.notes,
            }
        )
    custom = custom_provider_configured()
    base = os.environ.get(CUSTOM_ENV_KEYS["base_url"], "").strip()
    model = os.environ.get(CUSTOM_ENV_KEYS["model"], "").strip()
    rows.append(
        {
            "id": "custom",
            "label": "Custom OpenAI-compatible",
            "base_url": base or "(not set)",
            "default_model": model or "(not set)",
            "env_key_field": CUSTOM_ENV_KEYS["api_key"],
            "openai_compatible": True,
            "configured": custom,
            "notes": "Prepended to scheduler failover when base URL, key, and model are set.",
            "env_keys": CUSTOM_ENV_KEYS,
        }
    )
    return rows
