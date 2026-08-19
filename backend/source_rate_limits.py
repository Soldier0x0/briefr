"""Per-source outbound API pacing derived from official provider documentation.

BRIEFR never drops requests for rate limits — callers wait in the queue until
a slot opens. Intervals here are minimum spacing between requests for each
pacing group (conservative defaults when docs only publish daily/monthly caps).

References:
- NVD: https://nvd.nist.gov/developers/start (5 req/30s w/o key, 50/30s w/ key)
- Groq: https://console.groq.com/docs/rate-limits
- Gemini: https://ai.google.dev/gemini-api/docs/rate-limits
- Cerebras: https://inference-docs.cerebras.ai/
- OpenRouter: https://openrouter.ai/docs/api-reference/limits
- VirusTotal: https://docs.virustotal.com/reference/public-vs-premium-api
- GitHub REST: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- AbuseIPDB: https://docs.abuseipdb.com/ (1,000 checks/day free)
- GreyNoise: https://docs.greynoise.io/docs/using-the-greynoise-community-api
- OTX: https://otx.alienvault.com/api (10,000 req/hour with API key)
- Anthropic: https://docs.anthropic.com/en/api/rate-limits
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourcePacing:
    min_interval_seconds: float
    max_concurrent: int = 1
    docs_url: str = ""
    notes: str = ""


def _nvd_interval() -> float:
    # NVD publishes 50/30s (key) and 5/30s (anon). Use 60s divisor for headroom.
    if os.environ.get("NVD_API_KEY", "").strip():
        return 60.0 / 50.0
    return 60.0 / 5.0


def _github_interval() -> float:
    if os.environ.get("GITHUB_TOKEN", "").strip():
        return 3600.0 / 5000.0  # 5,000 req/hour authenticated
    return 3600.0 / 60.0  # 60 req/hour unauthenticated (GitHub REST + raw)


def get_openrouter_daily_limit() -> int | None:
    """OpenRouter free tier: 50 req/day without credits; override via env."""
    raw = os.environ.get("OPENROUTER_DAILY_LIMIT", "50").strip()
    if not raw or raw.lower() in ("none", "0", "unlimited"):
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return 50


# Pacing profile key -> limits. Multiple circuit sources map via resolve_pacing_key().
PACING_PROFILES: dict[str, SourcePacing] = {
    "nvd": SourcePacing(
        min_interval_seconds=6.0,
        docs_url="https://nvd.nist.gov/developers/start",
        notes="Overridden at runtime when NVD_API_KEY is set (conservative vs 50/30s).",
    ),
    "groq": SourcePacing(
        min_interval_seconds=15.0,
        docs_url="https://console.groq.com/docs/rate-limits",
        notes="openai/gpt-oss-20b TPM is usually tighter than RPM.",
    ),
    "gemini": SourcePacing(
        min_interval_seconds=1.0,
        docs_url="https://ai.google.dev/gemini-api/docs/rate-limits",
        notes="Flash-Lite free tier; conservative default spacing.",
    ),
    "cerebras": SourcePacing(
        min_interval_seconds=1.0,
        docs_url="https://inference-docs.cerebras.ai/",
        notes="Free-tier overflow; conservative default spacing.",
    ),
    "openrouter": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://openrouter.ai/docs/api-reference/limits",
        notes="`:free` models last resort; conservative spacing.",
    ),
    "anthropic": SourcePacing(
        min_interval_seconds=1.0,
        docs_url="https://docs.anthropic.com/en/api/rate-limits",
        notes="Legacy profile; no longer used by the LLM router.",
    ),
    "virustotal": SourcePacing(
        min_interval_seconds=15.0,
        docs_url="https://docs.virustotal.com/reference/public-vs-premium-api",
        notes="Public API: 4 requests/minute.",
    ),
    "abuseipdb": SourcePacing(
        min_interval_seconds=0.5,
        docs_url="https://docs.abuseipdb.com/",
        notes="Daily quota (1,000/day free) enforced separately in tracking.has_quota.",
    ),
    "greynoise": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://docs.greynoise.io/docs/using-the-greynoise-community-api",
        notes="50 lookups/week on free Community API.",
    ),
    "github": SourcePacing(
        min_interval_seconds=0.75,
        docs_url="https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api",
        notes="Faster with GITHUB_TOKEN (5,000 req/hour).",
    ),
    "otx": SourcePacing(
        min_interval_seconds=0.5,
        docs_url="https://otx.alienvault.com/api",
        notes="10,000 req/hour with API key; BRIEFR targets ~7,200/hour (2 req/sec).",
    ),
    "epss": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://www.first.org/epss/api",
        notes="No published per-minute cap; scheduler backfill spacing.",
    ),
    "osv": SourcePacing(
        min_interval_seconds=0.25,
        docs_url="https://google.github.io/osv.dev/api/",
    ),
    "kev": SourcePacing(
        min_interval_seconds=0.0,
        docs_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        notes="Static JSON; no published rate limit.",
    ),
    "mitre": SourcePacing(
        min_interval_seconds=1.0,
        max_concurrent=2,
        docs_url="https://github.com/mitre/cti",
        notes="Large GitHub raw downloads.",
    ),
    "rss": SourcePacing(
        min_interval_seconds=0.5,
        max_concurrent=3,
        notes="Parallel RSS fetches with modest spacing.",
    ),
    "webhook": SourcePacing(
        min_interval_seconds=0.5,
        max_concurrent=2,
        notes="Outbound Discord/Telegram/custom webhooks.",
    ),
    "sploitus": SourcePacing(min_interval_seconds=1.0),
    "circl": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://cve.circl.lu/",
        notes="abuse.ch fair-use spacing (~1 req/2s).",
    ),
    "malwarebazaar": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://bazaar.abuse.ch/api/",
        notes="abuse.ch fair-use spacing (~1 req/2s).",
    ),
    "urlhaus": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://urlhaus.abuse.ch/api/",
        notes="abuse.ch fair-use spacing (~1 req/2s).",
    ),
    "threatfox": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://threatfox.abuse.ch/api/",
        notes="abuse.ch fair-use spacing (~1 req/2s).",
    ),
    "feodo": SourcePacing(
        min_interval_seconds=2.0,
        docs_url="https://feodotracker.abuse.ch/blocklist/",
        notes="Public CC0 CSV; abuse.ch fair-use spacing.",
    ),
    "phishtank": SourcePacing(
        min_interval_seconds=5.0,
        docs_url="https://phishtank.org/developer_info.php",
        notes="Community CSV; optional PHISHTANK_APP_KEY for higher limits.",
    ),
    "tranco": SourcePacing(
        min_interval_seconds=30.0,
        docs_url="https://tranco-list.eu/",
        notes="Daily top-1M ZIP download; weekly import default.",
    ),
    "vulncheck": SourcePacing(
        min_interval_seconds=60.0 / 1000.0,
        docs_url="https://docs.vulncheck.com/",
        notes="Community tier ~1,000 req/min; conservative default spacing.",
    ),
    "default": SourcePacing(min_interval_seconds=1.0),
}

# Circuit-breaker source id -> pacing profile
_SOURCE_ALIASES: dict[str, str] = {
    "epss_bulk": "epss",
    "poc_github": "github",
    "cvelistv5": "github",
    "vulnrichment": "github",
    "metasploit": "github",
    "nuclei": "github",
    "exploitdb": "github",
    "atlas": "github",
}


def resolve_pacing_key(source: str) -> str:
    if source.startswith("rss:"):
        return "rss"
    if source.startswith("webhook."):
        return "webhook"
    return _SOURCE_ALIASES.get(source, source)


_SOURCE_API_KEY_ENV: dict[str, str] = {
    "nvd": "NVD_API_KEY",
    "github": "GITHUB_TOKEN",
    "virustotal": "VIRUSTOTAL_API_KEY",
    "abuseipdb": "ABUSEIPDB_API_KEY",
    "greynoise": "GREYNOISE_API_KEY",
    "otx": "OTX_API_KEY",
    "circl": "CIRCL_API_KEY",
    "vulncheck": "VULNCHECK_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

PACING_OVERRIDE_SOURCES: tuple[str, ...] = (
    "nvd", "otx", "virustotal", "github", "greynoise", "abuseipdb",
    "groq", "gemini", "cerebras", "openrouter", "epss", "osv",
)

_PREMIUM_INTERVAL_FACTOR = 0.5


def resolve_pacing_tier() -> str:
    tier = os.environ.get("OUTBOUND_PACING_TIER", "free").strip().lower()
    return tier if tier in ("free", "premium_auto", "custom") else "free"


def _has_api_key_for_source(key: str) -> bool:
    env_key = _SOURCE_API_KEY_ENV.get(key)
    return bool(env_key and os.environ.get(env_key, "").strip())


def _parse_custom_overrides() -> dict[str, float]:
    raw = os.environ.get("OUTBOUND_PACING_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, float] = {}
    for source, value in parsed.items():
        try:
            out[str(source)] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return out


def _custom_override(key: str) -> SourcePacing | None:
    overrides = _parse_custom_overrides()
    if key not in overrides:
        return None
    base = PACING_PROFILES.get(key, PACING_PROFILES["default"])
    return SourcePacing(
        min_interval_seconds=overrides[key],
        max_concurrent=base.max_concurrent,
        docs_url=base.docs_url,
        notes="Custom operator override (OUTBOUND_PACING_OVERRIDES).",
    )


def _base_interval_for_key(key: str) -> float:
    profile = PACING_PROFILES.get(key, PACING_PROFILES["default"])
    interval = profile.min_interval_seconds
    if key == "nvd":
        interval = _nvd_interval()
    elif key == "github":
        interval = _github_interval()
    elif key == "groq":
        try:
            from ai.groq_config import groq_limits
            interval = groq_limits().min_interval_seconds
        except Exception:
            pass
    elif key == "gemini":
        try:
            from ai.llm_pacing import gemini_limits
            interval = gemini_limits().min_interval_seconds
        except Exception:
            pass
    elif key == "cerebras":
        try:
            from ai.llm_pacing import cerebras_limits
            interval = cerebras_limits().min_interval_seconds
        except Exception:
            pass
    elif key == "openrouter":
        try:
            from ai.llm_pacing import openrouter_limits
            interval = openrouter_limits().min_interval_seconds
        except Exception:
            pass
    return max(interval, 0.0)


def _premium_profile(key: str) -> SourcePacing:
    base = PACING_PROFILES.get(key, PACING_PROFILES["default"])
    interval = _base_interval_for_key(key) * _PREMIUM_INTERVAL_FACTOR
    return SourcePacing(
        min_interval_seconds=max(interval, 0.0),
        max_concurrent=base.max_concurrent,
        docs_url=base.docs_url,
        notes=base.notes,
    )


def pacing_defaults_payload() -> dict[str, Any]:
    return {
        "tier": resolve_pacing_tier(),
        "sources": {
            key: {
                "min_interval_seconds": _base_interval_for_key(key),
                "docs_url": PACING_PROFILES.get(key, PACING_PROFILES["default"]).docs_url,
                "has_api_key": _has_api_key_for_source(key),
            }
            for key in PACING_OVERRIDE_SOURCES
        },
        "premium_factor": _PREMIUM_INTERVAL_FACTOR,
    }


def get_source_pacing(source: str) -> SourcePacing:
    key = resolve_pacing_key(source)
    tier = resolve_pacing_tier()
    if tier == "custom":
        custom = _custom_override(key)
        if custom is not None:
            return custom
    if tier == "premium_auto" and _has_api_key_for_source(key):
        return _premium_profile(key)
    profile = PACING_PROFILES.get(key, PACING_PROFILES["default"])
    return SourcePacing(
        min_interval_seconds=_base_interval_for_key(key),
        max_concurrent=profile.max_concurrent,
        docs_url=profile.docs_url,
        notes=profile.notes,
    )


def get_otx_hourly_limit() -> int:
    """OTX authenticated tier: 10,000 requests/hour."""
    return max(1, int(os.environ.get("OTX_HOURLY_LIMIT", "10000")))


def get_min_interval(source: str) -> float:
    """Seconds to wait after the previous request to the same source."""
    return get_source_pacing(source).min_interval_seconds
