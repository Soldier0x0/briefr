"""Tests for server-local path validation helpers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from path_safety import (
    PathValidationError,
    resolve_backup_archive,
    resolve_intel_snapshot_bundle,
)


def test_resolve_intel_snapshot_bundle_accepts_allowed_file(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    bundle = allowed / "briefr-intel-demo.pgdump.gz"
    bundle.write_bytes(b"test")
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    resolved = resolve_intel_snapshot_bundle(str(bundle))
    assert resolved == bundle.resolve()


def test_resolve_intel_snapshot_bundle_rejects_outside_root(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    bundle = outside / "briefr-intel-demo.pgdump.gz"
    bundle.write_bytes(b"test")
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    with pytest.raises(PathValidationError, match="must be under"):
        resolve_intel_snapshot_bundle(str(bundle))


def test_resolve_intel_snapshot_bundle_rejects_bad_filename(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    bundle = allowed / "evil.pgdump.gz"
    bundle.write_bytes(b"test")
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    with pytest.raises(PathValidationError, match="invalid bundle filename"):
        resolve_intel_snapshot_bundle(str(bundle))


def test_resolve_intel_snapshot_bundle_rejects_relative_path(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    monkeypatch.setenv("INTEL_SNAPSHOT_IMPORT_DIRS", str(allowed))

    with pytest.raises(PathValidationError, match="absolute"):
        resolve_intel_snapshot_bundle("briefr-intel-demo.pgdump.gz")


def test_resolve_backup_archive_accepts_valid_name(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    archive = backup_dir / "briefr-20260729.tar.gz"
    archive.write_bytes(b"test")

    resolved = resolve_backup_archive("briefr-20260729.tar.gz", backup_dir=str(backup_dir))
    assert resolved == archive.resolve()


def test_resolve_backup_archive_rejects_invalid_pattern(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "notbriefr.tgz").write_bytes(b"test")

    with pytest.raises(PathValidationError, match="invalid bundle filename"):
        resolve_backup_archive("notbriefr.tgz", backup_dir=str(backup_dir))
