"""Campaign lifecycle computation (Correlation v2 §24.10, ADR-002 C-Evolve-1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

LIFECYCLE_EMERGING_DAYS = 7
LIFECYCLE_ACTIVE_DAYS = 14
LIFECYCLE_DECLINING_DAYS = 30
LIFECYCLE_STALE_PULSE_DAYS = 365


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = f"{text}T00:00:00+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _days_ago(dt: Optional[datetime], now: datetime) -> Optional[int]:
    if dt is None:
        return None
    return (now.date() - dt.date()).days


def _has_local_boosters(members: list[dict[str, Any]]) -> bool:
    return any(bool(m.get("is_kev")) or bool(m.get("has_poc")) for m in members)


def compute_campaign_lifecycle(
    *,
    pulse_created_date: Any,
    members: list[dict[str, Any]],
    member_observation_at: list[Any],
    now: Optional[datetime] = None,
) -> str:
    """
    Deterministic lifecycle from member recency + KEV/exploit/EPSS activity.

    members: dicts with is_kev, has_poc, published, modified, kev_date_added,
             epss_activity_at (latest EPSS history row datetime, optional).
    member_observation_at: OTX pulse/indicator observation times (pulse
        ``created_date`` on CVE links and ``observed_at`` on pulse IOCs).
        Ingest ``fetched_at`` is never used (CORR-PR-7 / D4).
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    pulse_dt = _parse_dt(pulse_created_date)
    pulse_age = _days_ago(pulse_dt, now)
    boosters = _has_local_boosters(members)

    if pulse_age is not None and pulse_age > LIFECYCLE_STALE_PULSE_DAYS and not boosters:
        return "stale"

    emerging_cutoff = now - timedelta(days=LIFECYCLE_EMERGING_DAYS)
    active_cutoff = now - timedelta(days=LIFECYCLE_ACTIVE_DAYS)
    declining_cutoff = now - timedelta(days=LIFECYCLE_DECLINING_DAYS)

    last_activity: Optional[datetime] = pulse_dt

    for observed in member_observation_at:
        obs_dt = _parse_dt(observed)
        if obs_dt and obs_dt >= emerging_cutoff:
            return "emerging"
        if obs_dt and (last_activity is None or obs_dt > last_activity):
            last_activity = obs_dt

    for member in members:
        for key in ("published", "modified"):
            dt = _parse_dt(member.get(key))
            if dt and dt >= emerging_cutoff:
                return "emerging"
            if dt and (last_activity is None or dt > last_activity):
                last_activity = dt

        if member.get("is_kev"):
            kev_dt = _parse_dt(member.get("kev_date_added"))
            if kev_dt:
                if kev_dt >= active_cutoff:
                    return "active"
                if last_activity is None or kev_dt > last_activity:
                    last_activity = kev_dt

        if member.get("has_poc"):
            poc_dt = _parse_dt(member.get("modified")) or _parse_dt(member.get("published"))
            if poc_dt and poc_dt >= active_cutoff:
                return "active"
            if poc_dt and (last_activity is None or poc_dt > last_activity):
                last_activity = poc_dt

        epss_dt = _parse_dt(member.get("epss_activity_at"))
        if epss_dt:
            if epss_dt >= active_cutoff:
                return "active"
            if last_activity is None or epss_dt > last_activity:
                last_activity = epss_dt

    if last_activity is None or last_activity < declining_cutoff:
        return "declining"

    return "active"


async def fetch_member_lifecycle_inputs(
    db, pulse_id: str, member_ids: list[str]
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Load member CVE rows + pulse link timestamps for lifecycle computation."""
    if not member_ids:
        return [], []

    placeholders = ",".join("?" * len(member_ids))
    member_rows = await db.execute_fetchall(
        f"""
        SELECT c.cve_id, c.is_kev, c.has_poc, c.published, c.modified,
               k.date_added AS kev_date_added
        FROM cves c
        LEFT JOIN kev_deadlines k ON k.cve_id = c.cve_id
        WHERE c.cve_id IN ({placeholders})
        """,
        tuple(member_ids),
    )
    epss_rows = await db.execute_fetchall(
        f"""
        SELECT cve_id, MAX(recorded_date) AS epss_activity_at
        FROM epss_history
        WHERE cve_id IN ({placeholders})
        GROUP BY cve_id
        """,
        tuple(member_ids),
    )
    epss_map = {r["cve_id"]: r["epss_activity_at"] for r in epss_rows}

    members: list[dict[str, Any]] = []
    for row in member_rows:
        item = dict(row)
        item["epss_activity_at"] = epss_map.get(row["cve_id"])
        members.append(item)

    link_rows = await db.execute_fetchall(
        f"""
        SELECT created_date FROM otx_cve_pulses
        WHERE pulse_id = ? AND cve_id IN ({placeholders})
        """,
        (pulse_id, *member_ids),
    )
    observation_at = [
        r["created_date"] for r in link_rows if (r["created_date"] or "").strip()
    ]

    ioc_rows = await db.execute_fetchall(
        """
        SELECT observed_at FROM otx_pulse_iocs
        WHERE pulse_id = ?
          AND observed_at IS NOT NULL
          AND observed_at != ''
        """,
        (pulse_id,),
    )
    observation_at.extend(r["observed_at"] for r in ioc_rows)
    return members, observation_at
