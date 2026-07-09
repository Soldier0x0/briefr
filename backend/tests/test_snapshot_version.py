"""Unit tests for intel snapshot versioning helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from snapshot_version import SNAPSHOT_FORMAT_VERSION, validate_format_version
from verify_intel_snapshot import verify_snapshot


def test_validate_format_version_accepts_v1():
    validate_format_version({"format_version": SNAPSHOT_FORMAT_VERSION, "bundle_kind": "briefr-intel"})


def test_validate_format_version_rejects_unknown():
    with pytest.raises(ValueError, match="unsupported"):
        validate_format_version({"format_version": 99})


def test_verify_manifest_only(tmp_path):
    manifest = {
        "format_version": SNAPSHOT_FORMAT_VERSION,
        "bundle_kind": "briefr-intel",
        "schema_revision": "009_app_settings",
        "row_counts": {"cves": 0},
    }
    path = tmp_path / "briefr-intel.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = verify_snapshot(None, manifest_path=path, skip_dump_catalog=True)
    assert loaded["format_version"] == SNAPSHOT_FORMAT_VERSION
