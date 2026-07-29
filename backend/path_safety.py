"""Resolve and validate server-local paths for admin file operations."""

from __future__ import annotations

import os
import re
from pathlib import Path

_INTEL_BUNDLE_RE = re.compile(r"briefr-intel-[^/\\]+\.pgdump\.gz")
_BACKUP_ARCHIVE_RE = re.compile(r"briefr-[^/\\]+\.tar\.gz(\.age)?")


class PathValidationError(ValueError):
    """Raised when an operator-supplied filesystem path fails policy checks."""


def _resolved_roots(raw: str, *, default: list[str]) -> list[Path]:
    if raw.strip():
        return [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]
    return [Path(p) for p in default]


def intel_snapshot_import_roots() -> list[Path]:
    return _resolved_roots(
        os.environ.get("INTEL_SNAPSHOT_IMPORT_DIRS", ""),
        default=[
            os.environ.get("INTEL_PUBLISH_DIR", "/var/lib/briefr/intel-publish"),
            os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups"),
        ],
    )


def resolve_under_roots(
    raw_path: str,
    *,
    allowed_roots: list[Path],
    filename_re: re.Pattern[str] | None = None,
    must_exist: bool = True,
) -> Path:
    if not raw_path or not str(raw_path).strip():
        raise PathValidationError("path is required")
    candidate = Path(str(raw_path).strip())
    if not candidate.is_absolute():
        raise PathValidationError("path must be absolute")

    roots = [root.expanduser().resolve() for root in allowed_roots]
    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise PathValidationError(f"file not found: {raw_path}") from exc

    if must_exist and not resolved.is_file():
        raise PathValidationError(f"not a file: {raw_path}")
    if not any(resolved.is_relative_to(root) for root in roots):
        allowed = ", ".join(str(root) for root in roots)
        raise PathValidationError(f"path must be under: {allowed}")
    if filename_re and not filename_re.fullmatch(resolved.name):
        raise PathValidationError(f"invalid bundle filename: {resolved.name}")
    return resolved


def resolve_intel_snapshot_bundle(raw_path: str) -> Path:
    return resolve_under_roots(
        raw_path,
        allowed_roots=intel_snapshot_import_roots(),
        filename_re=_INTEL_BUNDLE_RE,
    )


def resolve_backup_archive(
    filename: str,
    *,
    backup_dir: str | None = None,
) -> Path:
    root = Path(backup_dir or os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups"))
    return resolve_under_roots(
        str((root / Path(filename).name).resolve()),
        allowed_roots=[root],
        filename_re=_BACKUP_ARCHIVE_RE,
    )
