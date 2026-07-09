"""Unit tests for campaign lifecycle computation (C-Evolve-1)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation.lifecycle import compute_campaign_lifecycle


def _now() -> datetime:
    return datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_lifecycle_stale_old_pulse_no_boosters():
    old_pulse = (_now() - timedelta(days=400)).isoformat()
    result = compute_campaign_lifecycle(
        pulse_created_date=old_pulse,
        members=[{"is_kev": False, "has_poc": False}],
        member_link_fetched_at=[(_now() - timedelta(days=200)).isoformat()],
        now=_now(),
    )
    assert result == "stale"


def test_lifecycle_stale_pulse_with_kev_not_stale():
    old_pulse = (_now() - timedelta(days=400)).isoformat()
    result = compute_campaign_lifecycle(
        pulse_created_date=old_pulse,
        members=[{
            "is_kev": True,
            "has_poc": False,
            "kev_date_added": (_now() - timedelta(days=5)).date().isoformat(),
        }],
        member_link_fetched_at=[(_now() - timedelta(days=200)).isoformat()],
        now=_now(),
    )
    assert result == "active"


def test_lifecycle_emerging_new_member_link():
    result = compute_campaign_lifecycle(
        pulse_created_date=(_now() - timedelta(days=60)).isoformat(),
        members=[{"is_kev": False, "has_poc": False}],
        member_link_fetched_at=[(_now() - timedelta(days=2)).isoformat()],
        now=_now(),
    )
    assert result == "emerging"


def test_lifecycle_active_recent_kev():
    result = compute_campaign_lifecycle(
        pulse_created_date=(_now() - timedelta(days=60)).isoformat(),
        members=[{
            "is_kev": True,
            "has_poc": True,
            "kev_date_added": (_now() - timedelta(days=10)).date().isoformat(),
        }],
        member_link_fetched_at=[(_now() - timedelta(days=20)).isoformat()],
        now=_now(),
    )
    assert result == "active"


def test_lifecycle_declining_no_recent_activity():
    result = compute_campaign_lifecycle(
        pulse_created_date=(_now() - timedelta(days=90)).isoformat(),
        members=[{"is_kev": False, "has_poc": False, "published": "2025-01-01"}],
        member_link_fetched_at=[(_now() - timedelta(days=45)).isoformat()],
        now=_now(),
    )
    assert result == "declining"


def test_lifecycle_default_active():
    result = compute_campaign_lifecycle(
        pulse_created_date=(_now() - timedelta(days=20)).isoformat(),
        members=[{"is_kev": False, "has_poc": False, "published": "2026-06-20"}],
        member_link_fetched_at=[(_now() - timedelta(days=15)).isoformat()],
        now=_now(),
    )
    assert result == "active"
