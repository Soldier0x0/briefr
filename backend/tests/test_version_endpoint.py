"""Tests for GET /api/version build-info stamping."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def test_version_without_build_info(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BUILD_INFO_PATH", tmp_path / "missing.json")
    info = asyncio.run(main.app_version())
    assert info["version"] == main.app.version
    assert info["commit"] is None
    assert info["built_at"] is None


def test_version_with_stamped_build_info(tmp_path, monkeypatch):
    stamp = tmp_path / ".build-info.json"
    stamp.write_text(
        json.dumps({"commit": "abc1234", "built_at": "2026-06-10T19:00:00Z"})
    )
    monkeypatch.setattr(main, "BUILD_INFO_PATH", stamp)
    info = asyncio.run(main.app_version())
    assert info["commit"] == "abc1234"
    assert info["built_at"] == "2026-06-10T19:00:00Z"


def test_version_with_corrupt_build_info(tmp_path, monkeypatch):
    stamp = tmp_path / ".build-info.json"
    stamp.write_text("{not json")
    monkeypatch.setattr(main, "BUILD_INFO_PATH", stamp)
    info = asyncio.run(main.app_version())
    assert info["commit"] is None
