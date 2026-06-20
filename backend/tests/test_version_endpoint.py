"""Tests for GET /api/version build-info stamping."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Request

from main import app
from routers import meta


def _version_request() -> Request:
    # /api/version reads the app version off request.app (router split phase 3).
    return Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/api/version",
            "headers": [],
            "app": app,
        }
    )


def test_version_without_build_info(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "BUILD_INFO_PATH", tmp_path / "missing.json")
    info = asyncio.run(meta.app_version(_version_request()))
    assert info["version"] == app.version
    assert info["commit"] is None
    assert info["built_at"] is None


def test_version_with_stamped_build_info(tmp_path, monkeypatch):
    stamp = tmp_path / ".build-info.json"
    stamp.write_text(
        json.dumps({"commit": "abc1234", "built_at": "2026-06-10T19:00:00Z"})
    )
    monkeypatch.setattr(meta, "BUILD_INFO_PATH", stamp)
    info = asyncio.run(meta.app_version(_version_request()))
    assert info["commit"] == "abc1234"
    assert info["built_at"] == "2026-06-10T19:00:00Z"


def test_version_with_corrupt_build_info(tmp_path, monkeypatch):
    stamp = tmp_path / ".build-info.json"
    stamp.write_text("{not json")
    monkeypatch.setattr(meta, "BUILD_INFO_PATH", stamp)
    info = asyncio.run(meta.app_version(_version_request()))
    assert info["commit"] is None


def test_build_info_path_points_at_backend_dir():
    """meta.py lives in routers/ — the stamp file stays in backend/."""
    assert meta.BUILD_INFO_PATH == (
        Path(__file__).resolve().parents[1] / ".build-info.json"
    )
