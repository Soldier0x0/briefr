from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catchup_mode as cm
from ai.llm_pacing import limits_from_env
from correlation.config import get_correlation_precompute_max_per_run
from ml import embeddings as emb


def setup_function():
    cm.reset_catchup_for_tests()


def teardown_function():
    cm.reset_catchup_for_tests()


def _parse_z(value: str) -> datetime:
    assert value.endswith("Z")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_default_inactive():
    assert cm.is_catchup_active() is False
    st = cm.get_catchup_status()
    assert st["active"] is False
    assert st["started_at"] is None
    assert st["ends_at"] is None
    assert st["duration_hours"] is None
    assert st["started_by"] is None
    assert st["cleared_reason"] is None
    assert st["in_wind_down"] is False
    assert st["should_start_new_work"] is False
    assert st["db_persisted"] is True


def test_expire_marks_db_not_persisted():
    cm.start_catchup(duration_hours=1)
    assert cm.get_catchup_status()["db_persisted"] is False
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) - timedelta(seconds=1))
    st = cm.get_catchup_status()
    assert st["active"] is False
    assert st["cleared_reason"] == "expired"
    assert st["db_persisted"] is False


def test_start_default_six_hours():
    st = cm.start_catchup(duration_hours=None, started_by="op")
    assert st["active"] is True
    assert st["duration_hours"] == 6
    assert st["started_by"] == "op"
    assert cm.is_catchup_active() is True
    ends = _parse_z(st["ends_at"])
    started = _parse_z(st["started_at"])
    assert timedelta(hours=5, minutes=50) < (ends - started) < timedelta(hours=6, minutes=10)


def test_start_with_explicit_ends_at_sets_duration_hours():
    ends_at = datetime.now(timezone.utc) + timedelta(hours=2)
    st = cm.start_catchup(ends_at=ends_at)
    assert st["active"] is True
    assert 1.9 < st["duration_hours"] < 2.1
    assert st["ends_at"].endswith("Z")


def test_start_while_active_raises():
    cm.start_catchup(duration_hours=2)
    with pytest.raises(cm.CatchupConflictError):
        cm.start_catchup(duration_hours=2)


def test_stop_ends_early():
    cm.start_catchup(duration_hours=6)
    st = cm.stop_catchup(reason="ended_early")
    assert st["active"] is False
    assert st["cleared_reason"] == "ended_early"
    assert cm.is_catchup_active() is False


def test_expire_clears_active():
    cm.start_catchup(ends_at=datetime.now(timezone.utc) + timedelta(minutes=10), started_by="t")
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) - timedelta(seconds=1))
    assert cm.is_catchup_active() is False
    assert cm.get_catchup_status()["cleared_reason"] == "expired"


def test_effective_caps_and_headroom():
    assert cm.effective_embeddings_max_per_run(2000) == 2000
    assert cm.effective_correlation_precompute_max_per_run(500) == 500
    assert cm.effective_llm_headroom_pct(85) == 85
    cm.start_catchup(duration_hours=1)
    assert cm.effective_embeddings_max_per_run(2000) == 4000
    assert cm.effective_embeddings_max_per_run(3000) == 5000
    assert cm.effective_correlation_precompute_max_per_run(500) == 1000
    assert cm.effective_correlation_precompute_max_per_run(1500) == 2000
    assert cm.effective_llm_headroom_pct(85) == 95
    assert cm.effective_llm_headroom_pct(99) == 99
    assert cm.effective_llm_headroom_pct(100) == 100


def test_embeddings_getter_respects_catchup(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_MAX_PER_RUN", "2000")
    assert emb.get_embeddings_max_per_run() == 2000

    cm.start_catchup(duration_hours=1)

    assert emb.get_embeddings_max_per_run() == 4000


def test_correlation_precompute_getter_respects_catchup(monkeypatch):
    monkeypatch.setenv("CORRELATION_PRECOMPUTE_MAX_PER_RUN", "500")
    assert get_correlation_precompute_max_per_run() == 500

    cm.start_catchup(duration_hours=1)

    assert get_correlation_precompute_max_per_run() == 1000


def test_llm_limits_from_env_respects_catchup_headroom(monkeypatch):
    monkeypatch.setenv("CATCHUPTEST_RPM_LIMIT", "60")
    monkeypatch.setenv("CATCHUPTEST_TPM_LIMIT", "1000000")
    monkeypatch.setenv("CATCHUPTEST_ESTIMATED_TOKENS_PER_REQUEST", "1")
    monkeypatch.setenv("CATCHUPTEST_HEADROOM_PCT", "85")

    polite = limits_from_env("CATCHUPTEST", default_rpm=60, default_tpm=1000000)
    assert polite.headroom_pct == 85

    cm.start_catchup(duration_hours=1)
    active = limits_from_env("CATCHUPTEST", default_rpm=60, default_tpm=1000000)

    assert active.headroom_pct == 95
    assert active.min_interval_seconds < polite.min_interval_seconds


def test_reject_over_max_duration():
    with pytest.raises(cm.CatchupValidationError):
        cm.start_catchup(duration_hours=25)


def test_reject_past_ends_at():
    with pytest.raises(cm.CatchupValidationError):
        cm.start_catchup(ends_at=datetime.now(timezone.utc) - timedelta(seconds=1))


def test_in_wind_down():
    cm.start_catchup(duration_hours=1)
    cm._force_ends_at_for_tests(datetime.now(timezone.utc) + timedelta(seconds=60))
    st = cm.get_catchup_status()
    assert st["active"] is True
    assert st["in_wind_down"] is True
    assert st["should_start_new_work"] is False
