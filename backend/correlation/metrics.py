"""Nightly correlation quality metrics snapshot (CORR-PR-13 / spec §13)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from correlation.config import get_hub_cve_pulse_cap
from db.timeutil import utcnow_str


def _today() -> str:
    return date.today().isoformat()


def _cutoff_30d() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")


async def _scalar(db, sql: str, params: tuple = ()) -> int | float | None:
    rows = await db.execute_fetchall(sql, params)
    if not rows:
        return None
    row = rows[0]
    if isinstance(row, dict):
        return next(iter(row.values()))
    try:
        return row[0]
    except (KeyError, IndexError, TypeError):
        return dict(row)[next(iter(dict(row)))]


async def compute_correlation_metrics_snapshot(db) -> dict[str, Any]:
    """Compute one daily metrics row from current DB state."""
    from db.correlation import get_latest_correlation_metrics, upsert_correlation_metrics

    cutoff = _cutoff_30d()
    hub_cap = get_hub_cve_pulse_cap()

    from db.correlation import _is_postgres_connection

    pg = _is_postgres_connection(db)
    p1 = "$1" if pg else "?"

    suppressions_30d = int(
        await _scalar(
            db,
            f"SELECT COUNT(*) FROM correlation_suppressions WHERE created_at >= {p1}",
            (cutoff,),
        )
        or 0
    )
    feedback_confirm_30d = int(
        await _scalar(
            db,
            f"""
            SELECT COUNT(*) FROM correlation_feedback
            WHERE verdict = 'confirm' AND created_at >= {p1}
            """,
            (cutoff,),
        )
        or 0
    )
    feedback_reject_30d = int(
        await _scalar(
            db,
            f"""
            SELECT COUNT(*) FROM correlation_feedback
            WHERE verdict IN ('reject', 'resolve_conflict') AND created_at >= {p1}
            """,
            (cutoff,),
        )
        or 0
    )

    campaign_members = int(
        await _scalar(db, "SELECT COUNT(*) FROM correlation_campaign_members") or 0
    )
    surfaced_findings_30d = max(
        campaign_members + suppressions_30d + feedback_confirm_30d, 1
    )
    rejection_rate = round(suppressions_30d / surfaced_findings_30d, 4)
    confirmation_rate = round(feedback_confirm_30d / surfaced_findings_30d, 4)

    ip_iocs = int(
        await _scalar(
            db,
            """
            SELECT COUNT(*) FROM otx_pulse_iocs
            WHERE UPPER(ioc_type) IN ('IP', 'IPV4', 'IPV6')
            """,
        )
        or 0
    )
    total_iocs = int(await _scalar(db, "SELECT COUNT(*) FROM otx_pulse_iocs") or 0)
    weak_edge_ratio = round(ip_iocs / total_iocs, 4) if total_iocs else 0.0

    hub_suppressed_edge_count = int(
        await _scalar(
            db,
            f"SELECT COUNT(*) FROM ioc_degree WHERE cve_count >= {p1}",
            (hub_cap,),
        )
        or 0
    )

    total_degrees = int(await _scalar(db, "SELECT COUNT(*) FROM ioc_degree") or 0)
    ioc_degree_p95 = 0
    if total_degrees > 0:
        idx = max(0, int(total_degrees * 0.95) - 1)
        p95_rows = await db.execute_fetchall(
            f"SELECT cve_count FROM ioc_degree ORDER BY cve_count LIMIT 1 OFFSET {idx}"
        )
        if p95_rows:
            row = p95_rows[0]
            if isinstance(row, dict):
                ioc_degree_p95 = int(next(iter(row.values())))
            else:
                ioc_degree_p95 = int(dict(row)["cve_count"])

    avg_independent_sources = float(
        await _scalar(
            db,
            """
            SELECT AVG(COALESCE(independent_sources, 1))
            FROM correlation_campaigns
            WHERE retracted_at IS NULL
            """,
        )
        or 0.0
    )
    avg_independent_sources = round(avg_independent_sources, 2)

    cves_with_pulses = int(
        await _scalar(db, "SELECT COUNT(DISTINCT cve_id) FROM otx_cve_pulses") or 0
    )
    orphan_cve_ratio = 0.0
    if cves_with_pulses > 0:
        orphan_cves = int(
            await _scalar(
                db,
                """
                SELECT COUNT(DISTINCT cve_id) FROM otx_cve_pulses
                WHERE cve_id NOT IN (
                    SELECT DISTINCT cve_id FROM correlation_campaign_members
                )
                """,
            )
            or 0
        )
        orphan_cve_ratio = round(orphan_cves / cves_with_pulses, 4)

    campaigns_active = int(
        await _scalar(
            db,
            "SELECT COUNT(*) FROM correlation_campaigns WHERE retracted_at IS NULL",
        )
        or 0
    )
    campaigns_retracted = int(
        await _scalar(
            db,
            "SELECT COUNT(*) FROM correlation_campaigns WHERE retracted_at IS NOT NULL",
        )
        or 0
    )
    stale_campaigns = int(
        await _scalar(
            db,
            """
            SELECT COUNT(*) FROM correlation_campaigns
            WHERE retracted_at IS NULL AND lifecycle = 'stale'
            """,
        )
        or 0
    )
    stale_campaign_ratio = (
        round(stale_campaigns / campaigns_active, 4) if campaigns_active else 0.0
    )

    campaign_member_count = campaign_members

    yesterday = await get_latest_correlation_metrics(db, before_day=_today())
    prev_active = int(yesterday.get("campaigns_active") or 0) if yesterday else 0
    campaign_survival_rate = (
        round(campaigns_active / prev_active, 4) if prev_active else 1.0
    )

    # Median evidence age from observed_at or fetched_at (days)
    total_ts = int(
        await _scalar(
            db,
            """
            SELECT COUNT(*) FROM otx_pulse_iocs
            WHERE COALESCE(observed_at, fetched_at) IS NOT NULL
            """,
        )
        or 0
    )
    median_evidence_age_days = 0.0
    if total_ts > 0:
        mid_idx = total_ts // 2
        mid_rows = await db.execute_fetchall(
            f"""
            SELECT COALESCE(observed_at, fetched_at) AS ts
            FROM otx_pulse_iocs
            WHERE COALESCE(observed_at, fetched_at) IS NOT NULL
            ORDER BY ts
            LIMIT 1 OFFSET {mid_idx}
            """
        )
        if mid_rows:
            mid = mid_rows[0]
            ts_raw = mid["ts"] if isinstance(mid, dict) else dict(mid)["ts"]
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    median_evidence_age_days = round(
                        (datetime.now(timezone.utc) - ts).total_seconds() / 86400, 2
                    )
                except ValueError:
                    median_evidence_age_days = 0.0

    row = {
        "day": _today(),
        "computed_at": utcnow_str(),
        "suppressions_30d": suppressions_30d,
        "feedback_confirm_30d": feedback_confirm_30d,
        "feedback_reject_30d": feedback_reject_30d,
        "surfaced_findings_30d": surfaced_findings_30d,
        "rejection_rate": rejection_rate,
        "confirmation_rate": confirmation_rate,
        "weak_edge_ratio": weak_edge_ratio,
        "hub_suppressed_edge_count": hub_suppressed_edge_count,
        "ioc_degree_p95": ioc_degree_p95,
        "avg_independent_sources": avg_independent_sources,
        "orphan_cve_ratio": orphan_cve_ratio,
        "campaigns_active": campaigns_active,
        "campaigns_retracted": campaigns_retracted,
        "campaign_survival_rate": campaign_survival_rate,
        "campaign_member_count": campaign_member_count,
        "stale_campaign_ratio": stale_campaign_ratio,
        "median_evidence_age_days": median_evidence_age_days,
    }
    await upsert_correlation_metrics(db, row)
    return row


async def snapshot_correlation_metrics(db) -> dict[str, Any]:
    """Public entry: compute and persist today's metrics row."""
    return await compute_correlation_metrics_snapshot(db)
