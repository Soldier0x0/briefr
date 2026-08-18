"""Admin dashboard API — shared helpers and constants.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import aiosqlite

from config_schema import SCHEDULER_RESCHEDULE_KEYS
from database import get_db
from redact import mask_secret_value, mask_url_value
from scheduler_locks import job_run_in_flight, locked_jobs
from settings import settings

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BUILD_INFO_PATH = _BACKEND_ROOT / ".build-info.json"
_DOTENV_PATH = _BACKEND_ROOT / ".env"

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")

_backup_running = asyncio.Event()

# WRITABLE_CONFIG_KEYS / INTEGER_KEYS / RESTART_REQUIRED_KEYS now come from
# config_schema.py (single source of truth — see that module for the full
# field list with help text and bounds).

def _read_build_info() -> dict[str, Any]:
    try:
        with _BUILD_INFO_PATH.open() as f:
            return json.load(f)
    except Exception:
        return {}


def _mask_key(value: str) -> str:
    """Mask secrets for GET /config display (first4…last4)."""
    return mask_secret_value(value)


def _mask_url(value: str) -> str:
    return mask_url_value(value)


def _mask_config_response_value(key: str, value: str) -> str:
    from redact import mask_config_value

    return mask_config_value(key, value)


def _propagate_to_settings(key: str, value: str) -> None:
    """Push a freshly-written env value into the live `settings` object so
    non-restart-required keys take effect immediately instead of only on
    next process start (settings is read from os.environ once at import).

    Note: CORS middleware reads `settings.allowed_origins_list` at startup —
    ALLOWED_ORIGINS changes still require a backend restart."""
    attr = key.lower()
    if not hasattr(settings, attr):
        return
    try:
        current = getattr(settings, attr)
        if isinstance(current, bool):
            setattr(settings, attr, value.lower() not in ("0", "false", "no", "off"))
        elif isinstance(current, int):
            setattr(settings, attr, int(value))
        else:
            setattr(settings, attr, value)
    except Exception:
        pass


def _apply_config_side_effects(keys: list[str]) -> dict[str, Any]:
    """Reschedule scheduler jobs for interval/cron keys after env write."""
    reschedule_keys = [k for k in keys if k in SCHEDULER_RESCHEDULE_KEYS]
    if not reschedule_keys:
        return {"rescheduled_jobs": [], "skipped_jobs": [], "scheduler_running": False}
    sched = _get_scheduler_module()
    result = sched.reschedule_jobs_for_keys(reschedule_keys)
    return {
        "rescheduled_jobs": result.get("rescheduled", []),
        "skipped_jobs": result.get("skipped", []),
        "scheduler_running": result.get("scheduler_running", False),
    }


def _env_flag_on(value: str | None, *, default: str = "0") -> bool:
    return (value if value is not None else default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _couple_embeddings_auto_on_enable(
    changed: list[tuple[str, str]],
    *,
    previous_enabled: bool,
) -> list[tuple[str, str]]:
    """When embeddings flip off→on, also set AUTO_ON_INGEST=1 unless explicitly set."""
    by_key = {k: v for k, v in changed}
    if "EMBEDDINGS_ENABLED" not in by_key:
        return changed
    if not _env_flag_on(by_key["EMBEDDINGS_ENABLED"]):
        return changed
    if previous_enabled:
        return changed
    if "EMBEDDINGS_AUTO_ON_INGEST" in by_key:
        return changed
    return list(changed) + [("EMBEDDINGS_AUTO_ON_INGEST", "1")]


def _config_apply_message(
    keys: list[str],
    *,
    restart_needed: bool,
    side_effects: dict[str, Any],
) -> str:
    reschedule_keys = [k for k in keys if k in SCHEDULER_RESCHEDULE_KEYS]
    rescheduled = side_effects.get("rescheduled_jobs") or []
    if restart_needed:
        return f"Applied {len(keys)} key(s); restarting backend"
    if reschedule_keys and rescheduled:
        return (
            f"Applied {len(keys)} key(s) — scheduler jobs rescheduled "
            f"({', '.join(rescheduled[:5])}{'…' if len(rescheduled) > 5 else ''})"
        )
    if reschedule_keys:
        return (
            f"Applied {len(keys)} key(s) — saved; scheduler will pick up intervals "
            "on next backend restart"
        )
    return f"Applied {len(keys)} key(s) — active now"


def _age_seconds(ts: float | None) -> float | None:
    if ts is None:
        return None
    return time.time() - ts


def _iso_to_age_seconds(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _get_scheduler_module():
    import scheduler as _sched
    return _sched


def _job_lock_held(job_id: str) -> bool:
    return job_run_in_flight(job_id)


_OPT_IN_DISABLED_JOBS = {
    "embeddings_backfill": ("EMBEDDINGS_ENABLED", "0"),
    "llm_product_extraction": ("LLM_PRODUCT_EXTRACTION_ENABLED", "0"),
    "detection_context_sync": ("DETECTION_CONTEXT_SYNC_ENABLED", "0"),
    "detection_context_llm": ("DETECTION_CONTEXT_LLM_ENABLED", "0"),
    "sigmahq_index_sync": ("SIGMAHQ_INDEX_SYNC_ENABLED", "1"),  # default on
    "exploit_sources_sync": ("EXPLOIT_SOURCES_SYNC_ENABLED", "1"),  # enabled=1 means NOT disabled
}


def _job_is_disabled(job_id: str) -> bool:
    """Return True if the job is env-gated and its gate is off."""
    gate = _OPT_IN_DISABLED_JOBS.get(job_id)
    if not gate:
        return False
    env_key, default_value = gate
    current = os.environ.get(env_key, default_value)
    return current.lower() in ("0", "false", "no", "off")


async def _get_job_last_run(db: aiosqlite.Connection, job_id: str) -> list[dict[str, Any]]:
    """Return history array (newest first), or empty list if none."""
    try:
        rows = await db.execute_fetchall(
            "SELECT value FROM sync_state WHERE key = ?",
            (f"scheduler.last_run.{job_id}",),
        )
        if not rows:
            return []
        raw = json.loads(rows[0]["value"])
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            # Migrate old single-dict format
            return [raw]
        return []
    except Exception:
        return []


def _schedule_cadence_for_job(job: Any) -> str:
    """Human-readable cadence from the APScheduler trigger (for admin UI)."""
    trigger = job.trigger
    tz = getattr(trigger, "timezone", None)
    tz_label = str(tz) if tz is not None else "UTC"
    if isinstance(trigger, IntervalTrigger):
        total = int(trigger.interval.total_seconds())
        if total >= 86400 and total % 86400 == 0:
            days = total // 86400
            unit = f"{days} day{'s' if days != 1 else ''}"
        elif total >= 3600 and total % 3600 == 0:
            hours = total // 3600
            unit = f"{hours} hour{'s' if hours != 1 else ''}"
        elif total >= 60 and total % 60 == 0:
            minutes = total // 60
            unit = f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            unit = f"{int(total)} seconds"
        return f"Every {unit} ({tz_label})"
    if isinstance(trigger, CronTrigger):
        fields = getattr(trigger, "fields", None)
        if fields:
            dow = getattr(fields, "day_of_week", None)
            hour = getattr(fields, "hour", None)
            minute = getattr(fields, "minute", None)
            if dow is not None and str(dow) not in ("*", "None"):
                hh = hour.expressions[0].values[0] if hour and hour.expressions else 0
                mm = minute.expressions[0].values[0] if minute and minute.expressions else 0
                return f"Weekly {str(dow).title()} {hh:02d}:{mm:02d} ({tz_label})"
            if hour is not None and minute is not None:
                try:
                    hh = hour.expressions[0].values[0]
                    mm = minute.expressions[0].values[0]
                    return f"Daily {hh:02d}:{mm:02d} ({tz_label})"
                except (AttributeError, IndexError, TypeError):
                    pass
        return f"Cron schedule ({tz_label})"
    return "Scheduled"


def _job_interval_seconds(job: Any) -> float | None:
    trigger = job.trigger
    if isinstance(trigger, IntervalTrigger):
        return float(trigger.interval.total_seconds())
    return None


def _build_job_info(job: Any, history: list[dict]) -> dict[str, Any]:
    paused = job.next_run_time is None
    lock_held = _job_lock_held(job.id)
    disabled = _job_is_disabled(job.id)
    next_run = None
    if job.next_run_time is not None:
        try:
            next_run = job.next_run_time.astimezone(timezone.utc).isoformat()
        except Exception:
            next_run = str(job.next_run_time)

    if disabled:
        status = "DISABLED"
    elif lock_held:
        status = "LOCKED"
    elif paused:
        status = "PAUSED"
    else:
        status = "ACTIVE"

    latest = history[0] if history else {}
    sched = _get_scheduler_module()
    progress = getattr(sched, "_job_progress", {}).get(job.id, "")

    stuck_warning = False
    if lock_held:
        from ai.llm_job_state import lock_started_at
        started = lock_started_at(job.id)
        if started is not None:
            interval = _job_interval_seconds(job)
            if interval and (time.time() - started) > 3 * interval:
                stuck_warning = True

    llm_state: dict[str, Any] = {}
    if lock_held:
        try:
            from ai.llm_job_state import get_job_llm_state, is_llm_job
            if is_llm_job(job.id):
                llm_state = get_job_llm_state(job.id) or {}
        except Exception:
            pass

    payload = {
        "id": job.id,
        "name": job.name,
        "schedule_cadence": _schedule_cadence_for_job(job),
        "next_run_time": next_run,
        "paused": paused,
        "lock_held": lock_held,
        "status": status,
        "progress_message": progress,
        "stuck_warning": stuck_warning,
        "last_run_utc": latest.get("last_run_utc") or latest.get("started_at"),
        "last_run_duration_seconds": latest.get("duration_seconds"),
        "last_run_records_upserted": latest.get("records_upserted"),
        "last_run_had_error": latest.get("had_error"),
        "last_error_message": (latest.get("error_message") or "")[:500],
        "last_run_id": latest.get("run_id") or "",
        "run_history": history,
    }
    if llm_state:
        payload["current_provider"] = llm_state.get("current_provider") or ""
        payload["providers_attempted"] = llm_state.get("providers_attempted") or []
    return payload


async def _get_all_scheduler_jobs() -> list[dict[str, Any]]:
    sched = _get_scheduler_module()
    scheduler = sched._scheduler
    if not scheduler:
        return []
    jobs = scheduler.get_jobs()
    db = await get_db()
    try:
        result = []
        for job in jobs:
            history = await _get_job_last_run(db, job.id)
            result.append(_build_job_info(job, history))
        return result
    finally:
        await db.close()


def _get_active_locks() -> list[dict[str, Any]]:
    """Return info on jobs whose lock is currently held."""
    return [{"job_id": job_id} for job_id in locked_jobs()]

