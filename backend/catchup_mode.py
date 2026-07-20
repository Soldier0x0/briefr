from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

from database import get_db, get_sync_state_value, set_sync_state_value

DEFAULT_DURATION_HOURS = 6
MAX_DURATION_HOURS = 24
WIND_DOWN_SECONDS = 300
CATCHUP_LLM_HEADROOM_PCT = 95
CATCHUP_MODE_LAST_KEY = "catchup_mode_last"

_EMBEDDINGS_MAX_CAP = 5000
_CORRELATION_PRECOMPUTE_MAX_CAP = 2000


class CatchupConflictError(Exception):
    pass


class CatchupValidationError(Exception):
    pass


@dataclass
class CatchupState:
    active: bool = False
    started_at: datetime | None = None
    ends_at: datetime | None = None
    duration_hours: float | None = None
    started_by: str | None = None
    cleared_reason: str | None = None


_lock = Lock()
_state = CatchupState()


def is_catchup_active() -> bool:
    with _lock:
        _expire_if_needed()
        return _state.active


def get_catchup_status() -> dict:
    with _lock:
        _expire_if_needed()
        return _status_locked()


def start_catchup(
    *,
    duration_hours: float | None = None,
    ends_at: datetime | None = None,
    started_by: str | None = None,
) -> dict:
    with _lock:
        _expire_if_needed()
        if _state.active:
            raise CatchupConflictError("Catch-up mode is already active")

        started_at = _utc_now()
        duration, end_time = _resolve_window(started_at, duration_hours, ends_at)
        _state.active = True
        _state.started_at = started_at
        _state.ends_at = end_time
        _state.duration_hours = duration
        _state.started_by = started_by
        _state.cleared_reason = None
        return _status_locked()


def stop_catchup(*, reason: str = "ended_early") -> dict:
    with _lock:
        _expire_if_needed()
        if _state.active:
            _state.active = False
            _state.cleared_reason = reason
        return _status_locked()


async def persist_catchup_status(status: dict | None = None) -> dict:
    payload = get_catchup_status() if status is None else status
    db = await get_db()
    try:
        await set_sync_state_value(db, CATCHUP_MODE_LAST_KEY, json.dumps(payload))
        await db.commit()
    finally:
        await db.close()
    return payload


async def clear_catchup_after_restart() -> dict:
    with _lock:
        global _state
        _state = CatchupState()

    db = await get_db()
    try:
        raw = await get_sync_state_value(db, CATCHUP_MODE_LAST_KEY)
        if not raw:
            return get_catchup_status()

        try:
            previous = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return get_catchup_status()

        if not _last_blob_looked_active(previous):
            return get_catchup_status()

        cleared = dict(previous)
        cleared["active"] = False
        cleared["cleared_reason"] = "restart"
        cleared["in_wind_down"] = False
        cleared["should_start_new_work"] = False
        await set_sync_state_value(db, CATCHUP_MODE_LAST_KEY, json.dumps(cleared))
        await db.commit()
        return cleared
    finally:
        await db.close()


def effective_embeddings_max_per_run(base: int) -> int:
    if not is_catchup_active():
        return base
    return min(base * 2, _EMBEDDINGS_MAX_CAP)


def effective_correlation_precompute_max_per_run(base: int) -> int:
    if not is_catchup_active():
        return base
    return min(base * 2, _CORRELATION_PRECOMPUTE_MAX_CAP)


def effective_llm_headroom_pct(base: int) -> int:
    if not is_catchup_active():
        return base
    return min(100, max(base, CATCHUP_LLM_HEADROOM_PCT))


def reset_catchup_for_tests() -> None:
    with _lock:
        global _state
        _state = CatchupState()


def _force_ends_at_for_tests(dt) -> None:
    with _lock:
        _state.ends_at = _as_utc(dt)


def _resolve_window(
    started_at: datetime,
    duration_hours: float | None,
    ends_at: datetime | None,
) -> tuple[float, datetime]:
    if duration_hours is not None and ends_at is not None:
        raise CatchupValidationError("Provide duration_hours or ends_at, not both")

    if ends_at is not None:
        end_time = _as_utc(ends_at)
        duration = (end_time - started_at).total_seconds() / 3600
    else:
        duration = DEFAULT_DURATION_HOURS if duration_hours is None else duration_hours
        end_time = started_at + timedelta(hours=duration)

    if duration <= 0:
        raise CatchupValidationError("Catch-up duration must be in the future")
    if duration > MAX_DURATION_HOURS:
        raise CatchupValidationError("Catch-up duration cannot exceed 24 hours")
    return duration, end_time


def _last_blob_looked_active(previous: Any) -> bool:
    if not isinstance(previous, dict) or previous.get("active") is not True:
        return False

    ends_at = previous.get("ends_at")
    if not isinstance(ends_at, str) or not ends_at:
        return False

    try:
        end_time = _parse_iso_datetime(ends_at)
    except ValueError:
        return False

    return end_time > _utc_now()


def _expire_if_needed() -> None:
    if _state.active and _state.ends_at is not None and _state.ends_at <= _utc_now():
        _state.active = False
        _state.cleared_reason = "expired"


def _status_locked() -> dict:
    in_wind_down = _in_wind_down_locked()
    return {
        "active": _state.active,
        "started_at": _format_utc(_state.started_at),
        "ends_at": _format_utc(_state.ends_at),
        "duration_hours": _state.duration_hours,
        "started_by": _state.started_by,
        "cleared_reason": _state.cleared_reason,
        "in_wind_down": in_wind_down,
        "should_start_new_work": _state.active and not in_wind_down,
    }


def _in_wind_down_locked() -> bool:
    if not _state.active or _state.ends_at is None:
        return False
    return (_state.ends_at - _utc_now()).total_seconds() <= WIND_DOWN_SECONDS


def _format_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_iso_datetime(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _utc_now() -> datetime:
    return datetime.now(UTC)
