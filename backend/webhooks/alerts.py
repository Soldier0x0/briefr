"""KEV-on-stack and backup dead-man alert rules (V1.3 Theme 8, V1.4 engine)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from backup.manager import BackupConfig, list_backups
from database import (
    filter_cves_matching_stack,
    get_db,
    get_sync_state_value,
    set_sync_state_value,
)
from preferences.repo import get_effective_stack_terms
from routers.cves import _stack_match_clause
from webhooks.destinations import EVENT_BACKUP_FAILURE, EVENT_KEV_ALERT
from webhooks.engine import clear_event_dedupe, dispatch_event
from webhooks.destinations import webhooks_enabled

logger = logging.getLogger(__name__)

ALERT_KEV_STACK = EVENT_KEV_ALERT
ALERT_BACKUP_DEADMAN = EVENT_BACKUP_FAILURE
BACKUP_DEADMAN_TARGET = "stale"
BACKUP_WATCH_BASELINE_KEY = "backup_deadman_baseline_utc"


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
