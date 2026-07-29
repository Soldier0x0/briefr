"""Tests for host_profile.collect_host_profile."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_collect_host_profile_returns_psutil_values(monkeypatch, tmp_path):
    from host_profile import collect_host_profile

    db_path = tmp_path / "briefr.db"
    db_path.write_bytes(b"x")
    profile = collect_host_profile(db_path=str(db_path))
    assert profile["cpu_count"] >= 1
    assert profile["memory_total_bytes"] > 0
    assert profile["disk_total_bytes"] > 0
    assert profile["disk_path"]
    assert profile["hostname"]
    assert profile["sampled_at"]
