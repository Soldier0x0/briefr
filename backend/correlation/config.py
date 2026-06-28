"""Correlation v2 configuration — env-backed defaults."""

from __future__ import annotations

import os

ENGINE_VERSION = "2.0"
CAMPAIGN_ALGORITHM_VERSION = "2.0.0-phase2"


def get_otx_ioc_sync_max_per_run() -> int:
    return max(1, int(os.environ.get("OTX_IOC_SYNC_MAX_PER_RUN", "500")))


def get_otx_cve_sync_days() -> int:
    return max(1, int(os.environ.get("OTX_CVE_SYNC_DAYS", "30")))


def get_correlation_cache_hours() -> float:
    return max(0.1, float(os.environ.get("CORRELATION_CACHE_HOURS", "6")))


def get_hub_cve_pulse_cap() -> int:
    return max(1, int(os.environ.get("CORRELATION_HUB_CVE_PULSE_CAP", "50")))


def get_correlation_confirm_enabled() -> bool:
    return os.environ.get("CORRELATION_CONFIRM_ENABLED", "1").strip() not in (
        "0",
        "false",
        "False",
    )


def get_max_campaign_members() -> int:
    return max(2, int(os.environ.get("CORRELATION_MAX_CAMPAIGN_MEMBERS", "25")))


def get_mitre_min_overlap() -> float:
    return max(0.0, float(os.environ.get("CORRELATION_MITRE_MIN_OVERLAP", "0.25")))
