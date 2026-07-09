"""Per-section intel provenance (FR1 — review §5.4)."""

from __future__ import annotations

import os
from typing import Any

from db.cache import get_cve_exploits_latest_fetched_at, get_feed_cache_timestamp
from db.types import DbConnection
from resilient_client import get_feed_health


def _source_health(source: str) -> dict[str, Any]:
    return get_feed_health().get(source, {})


def _circuit_open(source: str) -> bool:
    return bool(_source_health(source).get("circuit_open"))


def _latest_timestamp(*values: str | None) -> str | None:
    cleaned = [v.strip() for v in values if v and str(v).strip()]
    return max(cleaned) if cleaned else None


def _line(
    *,
    status: str,
    source: str,
    as_of: str | None = None,
) -> dict[str, str | None]:
    return {
        "status": status,
        "source": source,
        "as_of": as_of,
    }


async def derive_exploit_provenance(
    db: DbConnection,
    cve_id: str,
    *,
    used_nvd_fallback: bool = False,
) -> dict[str, str | None]:
    """
    Public exploit section — Sploitus + nightly exploit index + NVD refs.
    """
    key = cve_id.upper()
    exploit_index_at = await get_cve_exploits_latest_fetched_at(db, key)
    sploitus_at = await get_feed_cache_timestamp(db, f"sploitus:{key}")
    sploitus_down = _circuit_open("sploitus")

    if sploitus_down and not exploit_index_at and not sploitus_at and not used_nvd_fallback:
        health = _source_health("sploitus")
        return _line(
            status="source_unavailable",
            source="Sploitus",
            as_of=health.get("last_failure"),
        )

    if exploit_index_at or sploitus_at:
        return _line(
            status="checked",
            source="BRIEFR exploit index + Sploitus",
            as_of=_latest_timestamp(exploit_index_at, sploitus_at),
        )

    if used_nvd_fallback:
        return _line(
            status="checked",
            source="NVD references",
            as_of=None,
        )

    if sploitus_down:
        health = _source_health("sploitus")
        return _line(
            status="source_unavailable",
            source="Sploitus",
            as_of=health.get("last_failure"),
        )

    return _line(
        status="pending",
        source="Sploitus + BRIEFR exploit index",
        as_of=None,
    )


async def derive_detection_provenance(
    db: DbConnection,
    cve_id: str,
    *,
    technique_ids: list[str],
) -> dict[str, str | None]:
    """
    Detection section — community rules via GitHub + BRIEFR hunt starter.
    """
    key = cve_id.upper()
    sigma_at = await get_feed_cache_timestamp(db, f"sigma:{key}")
    sorted_tids = sorted(t.upper() for t in technique_ids if t)
    elastic_key = f"elastic:{','.join(sorted_tids[:5])}"
    elastic_at = await get_feed_cache_timestamp(db, elastic_key) if sorted_tids else None
    ctx_at = await get_feed_cache_timestamp(db, f"detection_ctx:{key}")
    github_down = _circuit_open("github")

    as_of = _latest_timestamp(sigma_at, elastic_at, ctx_at)
    has_community_cache = bool(sigma_at or elastic_at)

    if github_down and not has_community_cache:
        health = _source_health("github")
        return _line(
            status="source_unavailable",
            source="GitHub (SigmaHQ + Elastic) · BRIEFR templates still available",
            as_of=health.get("last_failure"),
        )

    if has_community_cache or ctx_at:
        return _line(
            status="checked",
            source="SigmaHQ + Elastic + BRIEFR",
            as_of=as_of,
        )

    return _line(
        status="checked",
        source="SigmaHQ + Elastic + BRIEFR",
        as_of=as_of,
    )


def derive_correlation_provenance(
    correlation: dict[str, Any],
    *,
    otx_configured: bool,
) -> dict[str, str | None]:
    """Correlation section — OTX pulse graph + nightly campaigns."""
    otx_status = str(correlation.get("otx_status") or "").lower()
    as_of = correlation.get("computed_at")

    if not otx_configured or otx_status == "not_configured":
        return _line(
            status="source_unavailable",
            source="AlienVault OTX",
            as_of=as_of,
        )

    if otx_status == "degraded" or correlation.get("error"):
        health = _source_health("otx")
        return _line(
            status="source_unavailable",
            source="AlienVault OTX + BRIEFR correlation",
            as_of=as_of or health.get("last_failure"),
        )

    if as_of:
        return _line(
            status="checked",
            source="AlienVault OTX + BRIEFR correlation",
            as_of=as_of,
        )

    if _circuit_open("otx"):
        health = _source_health("otx")
        return _line(
            status="source_unavailable",
            source="AlienVault OTX + BRIEFR correlation",
            as_of=health.get("last_failure"),
        )

    return _line(
        status="pending",
        source="AlienVault OTX + BRIEFR correlation",
        as_of=None,
    )


def otx_configured_from_env() -> bool:
    return bool(os.environ.get("OTX_API_KEY", "").strip())
