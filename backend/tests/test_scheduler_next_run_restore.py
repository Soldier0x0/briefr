"""M-9: ingest next_run_time restored from persisted last-run cadence."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import _OVERDUE_STARTUP_DELAY, _compute_restored_next_run

NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
HOUR = 3600.0


def test_mid_cycle_restart_resumes_cadence():
    """Last run 50min ago, 1h interval → due in 10min, earlier than the
    trigger default (now + 1h) → restored."""
    last = (NOW - timedelta(minutes=50)).isoformat()
    default = NOW + timedelta(hours=1)
    restored = _compute_restored_next_run(last, HOUR, NOW, default)
    assert restored == NOW + timedelta(minutes=10)


def test_overdue_job_runs_soon_but_not_immediately():
    last = (NOW - timedelta(hours=5)).isoformat()
    default = NOW + timedelta(hours=1)
    restored = _compute_restored_next_run(last, HOUR, NOW, default)
    assert restored == NOW + _OVERDUE_STARTUP_DELAY


def test_never_postpones_beyond_trigger_default():
    """Last run just happened → due ≈ now + interval, not sooner than the
    default → no modification."""
    last = NOW.isoformat()
    default = NOW + timedelta(hours=1)
    assert _compute_restored_next_run(last, HOUR, NOW, default) is None


def test_garbage_timestamp_returns_none():
    assert _compute_restored_next_run("not-a-date", HOUR, NOW, None) is None
    assert _compute_restored_next_run("", HOUR, NOW, None) is None


def test_naive_timestamp_treated_as_utc():
    last = (NOW - timedelta(minutes=30)).replace(tzinfo=None).isoformat()
    restored = _compute_restored_next_run(last, HOUR, NOW, None)
    assert restored == NOW + timedelta(minutes=30)
