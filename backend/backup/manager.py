"""
SQLite backup manager for BRIEFR.

- Online backup via sqlite3.Connection.backup() (WAL-safe)
- PRAGMA integrity_check before and after each backup
- Tar archives with DB, optional .env, and manifest JSON
- Retention pruning (default: keep latest 100)
- Rotating backup logs
- Automatic restore on startup when the live DB fails integrity check
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
DB_ARCHIVE_NAME = "briefr.db"
ENV_ARCHIVE_NAME = ".env"


@dataclass(frozen=True)
class BackupConfig:
    db_path: Path
    env_path: Path | None
    backup_dir: Path
    retention_count: int = 100
    log_path: Path | None = None
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 5
    enabled: bool = True

    @classmethod
    def from_env(cls, *, backend_dir: Path | None = None) -> BackupConfig:
        base = backend_dir or Path.cwd()
        dotenv_path = base / ".env"
        if dotenv_path.is_file():
            try:
                from dotenv import load_dotenv

                load_dotenv(dotenv_path)
            except ImportError:
                pass

        db_path = Path(os.environ.get("DB_PATH", "briefr.db"))
        if not db_path.is_absolute():
            db_path = (base / db_path).resolve()

        env_file = os.environ.get("ENV_FILE", str(base / ".env"))
        env_path = Path(env_file) if env_file else None
        if env_path and not env_path.is_file():
            env_path = None

        backup_dir = Path(
            os.environ.get("BACKUP_DIR", "/var/lib/briefr/backups")
        ).expanduser()
        if not backup_dir.is_absolute():
            backup_dir = (base / backup_dir).resolve()

        log_dir = backup_dir / "logs"
        retention = int(os.environ.get("BACKUP_RETENTION_COUNT", "100"))
        log_max = int(os.environ.get("BACKUP_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
        log_keep = int(os.environ.get("BACKUP_LOG_BACKUP_COUNT", "5"))
        enabled = os.environ.get("BACKUP_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

        return cls(
            db_path=db_path,
            env_path=env_path,
            backup_dir=backup_dir,
            retention_count=max(1, retention),
            log_path=log_dir / "backup.log",
            log_max_bytes=max(1024, log_max),
            log_backup_count=max(1, log_keep),
            enabled=enabled,
        )


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_db_integrity(db_path: Path) -> tuple[bool, str]:
    """Return (ok, message) using SQLite PRAGMA integrity_check."""
    if not db_path.is_file():
        return False, "database file does not exist"
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30.0)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            message = (row[0] if row else "").strip() or "unknown"
            return message.lower() == "ok", message
        finally:
            conn.close()
    except sqlite3.Error as exc:
        msg = str(exc).lower()
        if "malformed" in msg or "not a database" in msg or "corrupt" in msg:
            return False, str(exc)
        raise


def _online_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=60.0)
    try:
        dst = sqlite3.connect(str(destination))
        try:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()


def _write_manifest(
    path: Path,
    *,
    db_path: Path,
    db_sha256: str,
    env_included: bool,
    env_sha256: str | None,
    source_integrity: str,
    backup_integrity: str,
    reason: str,
) -> None:
    payload = {
        "version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "source_db": str(db_path),
        "source_integrity": source_integrity,
        "backup_integrity": backup_integrity,
        "db_sha256": db_sha256,
        "env_included": env_included,
        "env_sha256": env_sha256,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _create_archive_bundle(
    cfg: BackupConfig,
    *,
    reason: str,
) -> Path:
    if not cfg.db_path.is_file():
        raise FileNotFoundError(f"Database not found: {cfg.db_path}")

    source_ok, source_msg = check_db_integrity(cfg.db_path)
    if not source_ok:
        raise RuntimeError(
            f"Refusing to backup corrupt database ({cfg.db_path}): {source_msg}"
        )

    cfg.backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        cfg.backup_dir.chmod(0o750)
    except OSError:
        pass
    archive_name = f"briefr-{_utc_stamp()}.tar.gz"
    archive_path = cfg.backup_dir / archive_name

    with tempfile.TemporaryDirectory(prefix="briefr-backup-") as tmp:
        tmp_path = Path(tmp)
        staged_db = tmp_path / DB_ARCHIVE_NAME
        _online_backup(cfg.db_path, staged_db)

        backup_ok, backup_msg = check_db_integrity(staged_db)
        if not backup_ok:
            raise RuntimeError(f"Backup failed integrity check: {backup_msg}")

        db_sha = _sha256_file(staged_db)
        env_sha: str | None = None
        env_included = False
        if cfg.env_path and cfg.env_path.is_file():
            shutil.copy2(cfg.env_path, tmp_path / ENV_ARCHIVE_NAME)
            env_included = True
            env_sha = _sha256_file(tmp_path / ENV_ARCHIVE_NAME)

        _write_manifest(
            tmp_path / MANIFEST_NAME,
            db_path=cfg.db_path,
            db_sha256=db_sha,
            env_included=env_included,
            env_sha256=env_sha,
            source_integrity=source_msg,
            backup_integrity=backup_msg,
            reason=reason,
        )

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(staged_db, arcname=DB_ARCHIVE_NAME)
            tar.add(tmp_path / MANIFEST_NAME, arcname=MANIFEST_NAME)
            if env_included:
                tar.add(tmp_path / ENV_ARCHIVE_NAME, arcname=ENV_ARCHIVE_NAME)

    try:
        archive_path.chmod(0o600)
    except OSError:
        pass
    return archive_path


def prune_backups(backup_dir: Path, retention_count: int) -> list[Path]:
    """Delete oldest archives beyond retention_count; return removed paths."""
    if not backup_dir.is_dir():
        return []
    archives = sorted(
        backup_dir.glob("briefr-*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for old in archives[retention_count:]:
        old.unlink(missing_ok=True)
        removed.append(old)
    return removed


def rotate_log_file(
    log_path: Path,
    *,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Simple size-based log rotation with gzip history."""
    if not log_path.is_file():
        return
    if log_path.stat().st_size < max_bytes:
        return

    for idx in range(backup_count - 1, 0, -1):
        src = log_path.with_suffix(log_path.suffix + f".{idx}.gz")
        dst = log_path.with_suffix(log_path.suffix + f".{idx + 1}.gz")
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)

    rotated = log_path.with_suffix(log_path.suffix + ".1.gz")
    with log_path.open("rb") as src, gzip.open(rotated, "wb") as dst:
        shutil.copyfileobj(src, dst)
    log_path.write_text("", encoding="utf-8")


def _append_log(cfg: BackupConfig, message: str) -> None:
    if not cfg.log_path:
        return
    cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} {message}\n"
    with cfg.log_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    rotate_log_file(
        cfg.log_path,
        max_bytes=cfg.log_max_bytes,
        backup_count=cfg.log_backup_count,
    )


def run_backup(*, reason: str = "scheduled", config: BackupConfig | None = None) -> dict[str, Any]:
    cfg = config or BackupConfig.from_env()
    if not cfg.enabled:
        return {"status": "skipped", "reason": "BACKUP_ENABLED=0"}

    try:
        archive = _create_archive_bundle(cfg, reason=reason)
        removed = prune_backups(cfg.backup_dir, cfg.retention_count)
        result = {
            "status": "ok",
            "archive": str(archive),
            "reason": reason,
            "pruned": [str(p) for p in removed],
            "retention": cfg.retention_count,
        }
        _append_log(cfg, f"OK reason={reason} archive={archive.name} pruned={len(removed)}")
        logger.info("Backup created: %s", archive)
        return result
    except Exception as exc:
        _append_log(cfg, f"FAIL reason={reason} error={exc}")
        logger.error("Backup failed: %s", exc)
        raise


def list_backups(config: BackupConfig | None = None) -> list[dict[str, Any]]:
    cfg = config or BackupConfig.from_env()
    if not cfg.backup_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for archive in sorted(
        cfg.backup_dir.glob("briefr-*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        rows.append(
            {
                "archive": str(archive),
                "name": archive.name,
                "size_bytes": archive.stat().st_size,
                "mtime_utc": datetime.fromtimestamp(
                    archive.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return rows


def _verify_archive_contents(tmp_path: Path) -> tuple[bool, str]:
    db_file = tmp_path / DB_ARCHIVE_NAME
    if not db_file.is_file():
        return False, "archive missing briefr.db"
    return check_db_integrity(db_file)


def restore_backup(
    archive: Path,
    *,
    config: BackupConfig | None = None,
    force: bool = False,
) -> dict[str, Any]:
    cfg = config or BackupConfig.from_env()
    if not archive.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive}")

    with tempfile.TemporaryDirectory(prefix="briefr-restore-") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp_path)

        ok, msg = _verify_archive_contents(tmp_path)
        if not ok:
            raise RuntimeError(f"Backup archive failed integrity check: {msg}")

        if cfg.db_path.is_file() and not force:
            live_ok, live_msg = check_db_integrity(cfg.db_path)
            if live_ok:
                raise RuntimeError(
                    "Live database is healthy; pass force=True to overwrite"
                )

        cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        if cfg.db_path.is_file():
            corrupt_copy = cfg.db_path.with_suffix(
                cfg.db_path.suffix + f".corrupt.{_utc_stamp()}"
            )
            shutil.move(cfg.db_path, corrupt_copy)
            for sidecar in (f"{cfg.db_path}-wal", f"{cfg.db_path}-shm"):
                side_path = Path(sidecar)
                if side_path.is_file():
                    side_path.unlink()

        shutil.copy2(tmp_path / DB_ARCHIVE_NAME, cfg.db_path)

        env_restored = False
        env_archive = tmp_path / ENV_ARCHIVE_NAME
        if env_archive.is_file() and cfg.env_path:
            shutil.copy2(env_archive, cfg.env_path)
            env_restored = True

        restored_ok, restored_msg = check_db_integrity(cfg.db_path)
        if not restored_ok:
            raise RuntimeError(f"Restored database failed integrity check: {restored_msg}")

    result = {
        "status": "ok",
        "archive": str(archive),
        "db_path": str(cfg.db_path),
        "env_restored": env_restored,
        "integrity": restored_msg,
    }
    _append_log(cfg, f"RESTORE archive={archive.name} db={cfg.db_path}")
    logger.warning("Database restored from %s", archive)
    return result


def find_latest_valid_backup(config: BackupConfig | None = None) -> Path | None:
    cfg = config or BackupConfig.from_env()
    for entry in list_backups(cfg):
        archive = Path(entry["archive"])
        try:
            with tempfile.TemporaryDirectory(prefix="briefr-verify-") as tmp:
                tmp_path = Path(tmp)
                with tarfile.open(archive, "r:gz") as tar:
                    tar.extractall(tmp_path)
                ok, _ = _verify_archive_contents(tmp_path)
                if ok:
                    return archive
        except (OSError, tarfile.TarError, RuntimeError):
            continue
    return None


def ensure_db_or_restore(config: BackupConfig | None = None) -> dict[str, Any]:
    """
    On application startup: verify live DB integrity and restore from the
    newest valid backup when corruption is detected.
    """
    cfg = config or BackupConfig.from_env()
    if not cfg.enabled:
        return {"status": "skipped", "reason": "BACKUP_ENABLED=0"}

    if not cfg.db_path.is_file():
        return {"status": "no_db", "message": "database will be created on init"}

    ok, msg = check_db_integrity(cfg.db_path)
    if ok:
        return {"status": "healthy", "integrity": msg}

    logger.error("Database integrity check failed (%s): %s", cfg.db_path, msg)
    latest = find_latest_valid_backup(cfg)
    if not latest:
        raise RuntimeError(
            f"Database corrupt and no valid backup found in {cfg.backup_dir}"
        )

    result = restore_backup(latest, config=cfg, force=True)
    result["status"] = "restored"
    result["previous_integrity"] = msg
    return result
