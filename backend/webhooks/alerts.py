"""KEV-on-stack and backup dead-man alert rules (V1.3 Theme 8, V1.4 engine)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from backup.manager import BackupConfig, list_backups
from database import (
    filter_cves_matching_stack,
    get_db,
    get_recent_cve_changes,
    get_sync_state_value,
    list_pinned_cve_ids,
    set_sync_state_value,
)
from preferences.repo import get_effective_stack_terms
from routers.cves import _stack_match_clause
from webhooks.destinations import (
    EVENT_BACKUP_FAILURE,
    EVENT_KEV_ALERT,
    EVENT_KEV_BACKLOG,
    EVENT_IOC_WATCHLIST_HIT,
    EVENT_WATCHLIST_ALERT,
)
from webhooks.engine import clear_event_dedupe, dispatch_event
from webhooks.destinations import webhooks_enabled

logger = logging.getLogger(__name__)

ALERT_KEV_STACK = EVENT_KEV_ALERT
ALERT_BACKUP_DEADMAN = EVENT_BACKUP_FAILURE
ALERT_WATCHLIST = EVENT_WATCHLIST_ALERT
BACKUP_DEADMAN_TARGET = "stale"
BACKUP_WATCH_BASELINE_KEY = "backup_deadman_baseline_utc"
WATCHLIST_EPSS_MIN_DELTA = 0.05


def get_backup_interval_hours() -> int:
    raw = os.environ.get("BACKUP_INTERVAL_HOURS", "6").strip()
    try:
        hours = int(raw)
    except ValueError:
        hours = 6
    return max(1, hours)


def get_backup_deadman_threshold() -> timedelta:
    return timedelta(hours=get_backup_interval_hours() * 2)


def _backup_enabled() -> bool:
    return os.environ.get("BACKUP_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _parse_backup_mtime(mtime_utc: str) -> datetime | None:
    if not mtime_utc:
        return None
    try:
        parsed = datetime.fromisoformat(mtime_utc.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def last_successful_backup_utc() -> datetime | None:
    rows = list_backups(BackupConfig.from_env())
    if not rows:
        return None
    return _parse_backup_mtime(rows[0].get("mtime_utc", ""))


def _format_kev_alert(cve: dict) -> str:
    cve_id = cve.get("cve_id", "")
    severity = cve.get("severity") or "UNKNOWN"
    due = cve.get("kev_due_date") or "—"
    description = (cve.get("description") or cve.get("summary") or "").strip()
    if len(description) > 280:
        description = description[:277] + "..."
    terms = ", ".join(cve.get("matched_terms") or [])
    lines = [
        f"BRIEFR alert: {cve_id} added to CISA KEV and matches your stack",
        f"Severity: {severity}",
        f"KEV due date: {due}",
    ]
    if terms:
        lines.append(f"Matched stack terms: {terms}")
    if description:
        lines.append(description)
    return "\n".join(lines)


def _parse_score(value: object) -> float | None:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy_value(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def _format_watchlist_alert(
    *,
    cve_id: str,
    reason: str,
    detail: str,
    description: str = "",
) -> str:
    lines = [
        f"BRIEFR watchlist alert: {cve_id} — {reason}",
        detail,
    ]
    desc = (description or "").strip()
    if len(desc) > 280:
        desc = desc[:277] + "..."
    if desc:
        lines.append(desc)
    return "\n".join(lines)


async def _fetch_cve_blurb(db, cve_id: str) -> str:
    rows = await db.execute_fetchall(
        "SELECT description, summary FROM cves WHERE cve_id = ?",
        (cve_id.upper(),),
    )
    if not rows:
        return ""
    row = dict(rows[0])
    return (row.get("summary") or row.get("description") or "").strip()


async def process_watchlist_kev_alerts(newly_kev_ids: list[str]) -> int:
    """Alert when a pinned CVE enters CISA KEV."""
    if not newly_kev_ids or not webhooks_enabled():
        return 0

    db = await get_db()
    try:
        pinned = {cve_id.upper() for cve_id in await list_pinned_cve_ids(db)}
    finally:
        await db.close()

    if not pinned:
        return 0

    sent = 0
    for raw_id in newly_kev_ids:
        cve_id = raw_id.upper()
        if cve_id not in pinned:
            continue
        db = await get_db()
        try:
            description = await _fetch_cve_blurb(db, cve_id)
        finally:
            await db.close()
        result = await dispatch_event(
            EVENT_WATCHLIST_ALERT,
            _format_watchlist_alert(
                cve_id=cve_id,
                reason="added to CISA KEV",
                detail="Pinned CVE is now on the Known Exploited Vulnerabilities catalog.",
                description=description,
            ),
            dedupe_key=f"{cve_id}:kev",
        )
        if result.get("sent"):
            sent += 1
            logger.info("Watchlist KEV alert sent for %s", cve_id)
    return sent


async def process_watchlist_monitor_alerts(*, since_hours: int = 24) -> int:
    """Alert on significant changes to pinned CVEs (EPSS jump, PoC surfaced)."""
    if not webhooks_enabled():
        return 0

    db = await get_db()
    try:
        pinned = {cve_id.upper() for cve_id in await list_pinned_cve_ids(db)}
        if not pinned:
            return 0
        changes = await get_recent_cve_changes(db, since_hours=since_hours, limit=500)
    finally:
        await db.close()

    sent = 0
    for change in changes:
        cve_id = (change.get("cve_id") or "").upper()
        if cve_id not in pinned:
            continue
        field = change.get("field_name") or ""
        old_val = change.get("old_value")
        new_val = change.get("new_value")

        reason = ""
        detail = ""
        if field == "epss_score":
            old_score = _parse_score(old_val)
            new_score = _parse_score(new_val)
            if old_score is None or new_score is None:
                continue
            delta = new_score - old_score
            if delta < WATCHLIST_EPSS_MIN_DELTA:
                continue
            reason = "EPSS increased"
            detail = f"EPSS {old_score:.3f} → {new_score:.3f} (+{delta:.3f})"
        elif field == "has_poc":
            if _truthy_value(old_val) or not _truthy_value(new_val):
                continue
            reason = "proof-of-concept surfaced"
            detail = "Public exploit or PoC reference detected for this pinned CVE."
        else:
            continue

        db = await get_db()
        try:
            description = await _fetch_cve_blurb(db, cve_id)
        finally:
            await db.close()

        result = await dispatch_event(
            EVENT_WATCHLIST_ALERT,
            _format_watchlist_alert(
                cve_id=cve_id,
                reason=reason,
                detail=detail,
                description=description,
            ),
            dedupe_key=f"{cve_id}:{field}",
        )
        if result.get("sent"):
            sent += 1
            logger.info("Watchlist monitor alert sent for %s (%s)", cve_id, field)
    return sent


async def process_kev_stack_alerts(newly_kev_ids: list[str]) -> int:
    """Send one alert per CVE the first time it enters KEV and matches the stack."""
    if not newly_kev_ids or not webhooks_enabled():
        return 0

    db = await get_db()
    try:
        stack = await get_effective_stack_terms(db)
        clause, _, terms = _stack_match_clause(stack)
        if not clause or not terms:
            logger.debug("KEV stack alerts skipped: no stack terms configured")
            return 0

        matches = await filter_cves_matching_stack(db, newly_kev_ids, stack)
        candidates = []
        for cve in matches:
            cve["matched_terms"] = terms
            candidates.append(cve)
    finally:
        await db.close()

    sent = 0
    for cve in candidates:
        cve_id = cve["cve_id"]
        result = await dispatch_event(
            EVENT_KEV_ALERT,
            _format_kev_alert(cve),
            dedupe_key=cve_id,
        )
        if not result.get("sent"):
            logger.warning("KEV stack alert not delivered for %s: %s", cve_id, result)
            continue
        sent += 1
        logger.info("KEV stack alert sent for %s", cve_id)
    return sent


def _format_kev_backlog_alert(item: dict) -> str:
    cve_id = item.get("cve_id", "")
    technique_id = item.get("technique_id", "")
    technique_name = item.get("technique_name") or technique_id
    priority = (item.get("priority") or "high").upper()
    return (
        f"Detection backlog: new KEV gap on your stack — {cve_id} maps to "
        f"{technique_id} ({technique_name}) with no saved or community rule. "
        f"Priority: {priority}. Open Forge → Backlog to generate a hunt pack."
    )


async def process_kev_backlog_webhooks(items: list[dict]) -> int:
    """Notify subscribed destinations when new KEV gap backlog rows are created."""
    if not items or not webhooks_enabled():
        return 0

    sent = 0
    for item in items:
        cve_id = item.get("cve_id", "")
        technique_id = item.get("technique_id", "")
        if not cve_id or not technique_id:
            continue
        result = await dispatch_event(
            EVENT_KEV_BACKLOG,
            _format_kev_backlog_alert(item),
            dedupe_key=f"{cve_id}:{technique_id}",
        )
        if result.get("sent"):
            sent += 1
            logger.info("KEV backlog webhook sent for %s / %s", cve_id, technique_id)
    return sent


def _format_ioc_watchlist_hit(match: dict) -> str:
    ioc_value = match.get("ioc_value", "")
    ioc_type = (match.get("ioc_type") or "").upper()
    source = (match.get("source") or "").upper()
    detail = (match.get("detail") or "").strip()
    label = (match.get("label") or "").strip()
    head = f"IOC watchlist hit ({source}): {ioc_type} {ioc_value}"
    if label:
        head += f" [{label}]"
    if detail:
        head += f" — {detail[:200]}"
    return head


async def process_ioc_watchlist_hit_webhooks(matches: list[dict]) -> int:
    if not matches or not webhooks_enabled():
        return 0

    sent = 0
    for match in matches:
        user_id = match.get("user_id")
        ioc_value = match.get("ioc_value", "")
        source = match.get("source", "")
        if not user_id or not ioc_value or not source:
            continue
        result = await dispatch_event(
            EVENT_IOC_WATCHLIST_HIT,
            _format_ioc_watchlist_hit(match),
            dedupe_key=f"{user_id}:{ioc_value}:{source}",
        )
        if result.get("sent"):
            sent += 1
    return sent


async def check_backup_deadman() -> bool:
    """Warn when no successful backup exists within 2× BACKUP_INTERVAL_HOURS."""
    if not _backup_enabled() or not webhooks_enabled():
        return False

    threshold = get_backup_deadman_threshold()
    now = datetime.now(timezone.utc)
    last_backup = last_successful_backup_utc()

    db = await get_db()
    try:
        if last_backup is not None:
            age = now - last_backup
            if age <= threshold:
                await clear_event_dedupe(EVENT_BACKUP_FAILURE, BACKUP_DEADMAN_TARGET)
                return False
            stale_for = age
        else:
            baseline_raw = await get_sync_state_value(db, BACKUP_WATCH_BASELINE_KEY)
            if not baseline_raw:
                await set_sync_state_value(db, BACKUP_WATCH_BASELINE_KEY, now.isoformat())
                await db.commit()
                return False
            baseline = _parse_backup_mtime(baseline_raw)
            if baseline is None:
                baseline = now
            stale_for = now - baseline
            if stale_for <= threshold:
                return False
    finally:
        await db.close()

    hours = int(stale_for.total_seconds() // 3600)
    interval = get_backup_interval_hours()
    message = (
        "BRIEFR backup dead-man alert: no successful backup within "
        f"{interval * 2}h (last success ~{hours}h ago). "
        "Check `systemctl status briefr-backup.timer`, "
        "`journalctl -u briefr-backup`, and `/var/lib/briefr/backups`."
    )
    result = await dispatch_event(
        EVENT_BACKUP_FAILURE,
        message,
        dedupe_key=BACKUP_DEADMAN_TARGET,
    )
    if not result.get("sent"):
        logger.warning("Backup dead-man alert not delivered: %s", result)
        return False

    logger.warning("Backup dead-man alert sent (stale_for=%sh)", hours)
    return True
