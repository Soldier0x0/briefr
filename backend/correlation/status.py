"""Phase 5 operator diagnostics for correlation engine."""

from __future__ import annotations

from typing import Any

from correlation.campaigns import (
    CORRELATION_BUILD_WATERMARK_KEY,
    CORRELATION_LAST_RUN_KEY,
)
from database import get_sync_state_value


async def get_correlation_admin_status(db: Any) -> dict[str, Any]:
    """Last run, campaign counts, OTX IOC coverage, and ingest backlog."""
    last_run = await get_sync_state_value(db, CORRELATION_LAST_RUN_KEY)
    build_watermark = await get_sync_state_value(db, CORRELATION_BUILD_WATERMARK_KEY)

    campaign_rows = await db.execute_fetchall(
        """
        SELECT lifecycle, COUNT(*) AS cnt, AVG(member_count) AS avg_members
        FROM correlation_campaigns
        GROUP BY lifecycle
        """
    )
    lifecycle_counts: dict[str, int] = {}
    total_campaigns = 0
    member_sum = 0.0
    for row in campaign_rows:
        lifecycle = row["lifecycle"] or "active"
        count = int(row["cnt"] or 0)
        lifecycle_counts[lifecycle] = count
        total_campaigns += count
        member_sum += float(row["avg_members"] or 0) * count
    avg_members = round(member_sum / total_campaigns, 2) if total_campaigns else 0.0

    cve_total_row = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM cves")
    cve_total = int(cve_total_row[0]["cnt"]) if cve_total_row else 0

    cve_campaign_row = await db.execute_fetchall(
        """
        SELECT COUNT(DISTINCT cve_id) AS cnt
        FROM correlation_campaign_members
        """
    )
    cves_with_campaign = int(cve_campaign_row[0]["cnt"]) if cve_campaign_row else 0
    campaign_coverage_pct = (
        round(100.0 * cves_with_campaign / cve_total, 2) if cve_total else 0.0
    )

    pulse_linked_row = await db.execute_fetchall(
        "SELECT COUNT(DISTINCT pulse_id) AS cnt FROM otx_cve_pulses"
    )
    pulses_linked = int(pulse_linked_row[0]["cnt"]) if pulse_linked_row else 0

    pulse_ioc_row = await db.execute_fetchall(
        "SELECT COUNT(DISTINCT pulse_id) AS cnt FROM otx_pulse_iocs"
    )
    pulses_with_iocs = int(pulse_ioc_row[0]["cnt"]) if pulse_ioc_row else 0

    backlog_row = await db.execute_fetchall(
        """
        SELECT COUNT(DISTINCT ocp.pulse_id) AS cnt
        FROM otx_cve_pulses ocp
        WHERE NOT EXISTS (
            SELECT 1 FROM otx_pulse_iocs opi WHERE opi.pulse_id = ocp.pulse_id
        )
        """
    )
    ioc_backlog_pulses = int(backlog_row[0]["cnt"]) if backlog_row else 0

    otx_ioc_coverage_pct = (
        round(100.0 * pulses_with_iocs / pulses_linked, 2) if pulses_linked else 0.0
    )

    suppressions_row = await db.execute_fetchall(
        "SELECT COUNT(*) AS cnt FROM correlation_suppressions"
    )
    suppressions_count = int(suppressions_row[0]["cnt"]) if suppressions_row else 0

    from db.correlation import get_latest_correlation_metrics

    metrics = await get_latest_correlation_metrics(db)

    return {
        "last_run": last_run,
        "build_watermark": build_watermark,
        "campaigns": {
            "total": total_campaigns,
            "by_lifecycle": lifecycle_counts,
            "avg_members": avg_members,
        },
        "coverage": {
            "cves_total": cve_total,
            "cves_with_campaign": cves_with_campaign,
            "campaign_coverage_pct": campaign_coverage_pct,
            "otx_pulses_linked": pulses_linked,
            "otx_pulses_with_iocs": pulses_with_iocs,
            "otx_ioc_coverage_pct": otx_ioc_coverage_pct,
        },
        "backlog": {
            "ioc_sync_pending_pulses": ioc_backlog_pulses,
        },
        "suppressions_count": suppressions_count,
        "metrics": metrics,
        "features": {
            "clusters_api": "/api/correlation/clusters",
            "feed_campaign_sort_boost": True,
            "feed_campaign_sort_boost_gated": True,
            "cve_cluster_filter": True,
        },
    }
