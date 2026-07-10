"""Tests for scheduler config-key → job reschedule helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import _trigger_for_job, jobs_for_config_keys, reschedule_jobs_for_keys


def test_jobs_for_config_keys_dedupes_mitre_cron():
    jobs = jobs_for_config_keys(["MITRE_REFRESH_HOUR", "MITRE_REFRESH_MINUTE"])
    assert jobs == ["weekly_mitre_refresh"]


def test_jobs_for_config_keys_backup_updates_two_jobs():
    jobs = jobs_for_config_keys(["BACKUP_INTERVAL_HOURS"])
    assert set(jobs) == {"scheduled_backup", "backup_deadman_check"}


def test_trigger_for_job_nvd_reads_env(monkeypatch):
    monkeypatch.setenv("NVD_SYNC_INTERVAL_HOURS", "4")
    trigger = _trigger_for_job("nvd_incremental_sync")
    assert trigger is not None
    assert trigger.interval.total_seconds() == 4 * 3600


def test_reschedule_jobs_for_keys_when_scheduler_stopped():
    result = reschedule_jobs_for_keys(["NVD_SYNC_INTERVAL_HOURS"])
    assert result["scheduler_running"] is False
    assert result["rescheduled"] == []
    assert "nvd_incremental_sync" in result["skipped"]
