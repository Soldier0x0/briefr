"""
SQLite backup manager for BRIEFR.

- Online backup via sqlite3.Connection.backup() (WAL-safe)
- PRAGMA integrity_check before and after each backup
- Tar archives with DB, optional .env, and manifest JSON
- Optional age (X25519) archive encryption via BACKUP_AGE_KEY_FILE —
  the identity file must live OUTSIDE BACKUP_DIR (enforced) so stolen
  archive copies cannot be decrypted with what sits next to them
- Retention pruning (default: keep latest 100)
- Rotating backup logs
- Automatic restore on startup when the live DB fails integrity check
  (works for both plaintext .tar.gz and encrypted .tar.gz.age archives)
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

import pyrage
from pyrage import x25519

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
DB_ARCHIVE_NAME = "briefr.db"
ENV_ARCHIVE_NAME = ".env"
ENCRYPTED_ARCHIVE_SUFFIX = ".age"
ARCHIVE_GLOBS = ("briefr-*.tar.gz", "briefr-*.tar.gz.age")
# Production default written by deploy/briefr-backup.sh on first run.
# Deliberately outside BACKUP_DIR (/var/lib/briefr/backups).
DEFAULT_AGE_KEY_FILE = "/var/lib/briefr/keys/backup-age.key"


def _write_audit_sync(db_path: Path, actor: str, action: str, target: str) -> None:
    """Best-effort audit row from sync backup code (never fails the backup).

    Creates audit_log if missing: restores and pre-init backups can run
    before database.init_db() has seen the (restored) database file.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                "INSERT INTO audit_log (actor, action, target) VALUES (?, ?, ?)",
                (actor, action, target),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("Audit log write failed (%s %s): %s", action, target, exc)


def _safe_tar_extractall(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract tar contents into dest, rejecting path traversal (tar slip)."""
    dest_resolved = dest.resolve()
    if hasattr(tarfile, "data_filter"):
        tar.extractall(dest, filter="data")
        return
    for member in tar.getmembers():
        member_path = (dest_resolved / member.name).resolve()
        if os.path.commonpath([str(dest_resolved), str(member_path)]) != str(
            dest_resolved
        ):
            raise PermissionError(
                f"Attempted directory traversal in tar archive: {member.name!r}"
            )
    tar.extractall(dest)


def load_age_identity(key_path: Path) -> x25519.Identity:
    """Parse an age identity file (age-keygen format: # comments + secret key)."""
    if not key_path.is_file():
        raise FileNotFoundError(f"Backup age key file not found: {key_path}")
    for line in key_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return x25519.Identity.from_str(line)
    raise RuntimeError(f"No AGE-SECRET-KEY found in {key_path}")


def generate_age_key(key_path: Path) -> str:
    """Create a new age identity file (mode 0600) and return its public key."""
    if key_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing key: {key_path}")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        key_path.parent.chmod(0o700)
    except OSError:
        pass
    identity = x25519.Identity.generate()
    public_key = str(identity.to_public())
    body = (
        f"# created: {datetime.now(timezone.utc).isoformat()}\n"
        f"# public key: {public_key}\n"
        f"{identity}\n"
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(body)
    return public_key


def _resolve_age_key_path(base: Path) -> Path | None:
    """
    Resolve the age identity file from BACKUP_AGE_KEY_FILE.

    - Unset: use the production default path only when the file exists
      (dev machines keep writing plaintext archives, unchanged behavior).
    - Set to a path: keep it even when the file is missing so backups fail
      loudly instead of silently falling back to plaintext.
    - Set to empty string: encryption explicitly disabled.
    """
    raw = os.environ.get("BACKUP_AGE_KEY_FILE")
    if raw is None:
        default_key = Path(DEFAULT_AGE_KEY_FILE)
        return default_key if default_key.is_file() else None
    raw = raw.strip()
    if not raw:
        return None
    key_path = Path(raw).expanduser()
    if not key_path.is_absolute():
        key_path = (base / key_path).resolve()
    return key_path


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
    age_key_path: Path | None = None

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
            age_key_path=_resolve_age_key_path(base),
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
    encrypted: bool = False,
    age_public_key: str | None = None,
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
        "encrypted": encrypted,
        "age_public_key": age_public_key,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _check_age_key_location(cfg: BackupConfig) -> None:
    """The decryption key must never travel with (or inside) the archives."""
    if cfg.age_key_path is None:
        return
    key = cfg.age_key_path.resolve()
    backups = cfg.backup_dir.resolve()
    if key.is_relative_to(backups):
        raise RuntimeError(
            f"BACKUP_AGE_KEY_FILE must live outside BACKUP_DIR "
            f"(key={key}, backups={backups})"
        )


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

    recipient: x25519.Recipient | None = None
    age_public_key: str | None = None
    if cfg.age_key_path is not None:
        _check_age_key_location(cfg)
        recipient = load_age_identity(cfg.age_key_path).to_public()
        age_public_key = str(recipient)

    archive_name = f"briefr-{_utc_stamp()}.tar.gz"
    if recipient is not None:
        archive_name += ENCRYPTED_ARCHIVE_SUFFIX
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
            encrypted=recipient is not None,
            age_public_key=age_public_key,
        )

        tar_target = tmp_path / "bundle.tar.gz" if recipient is not None else archive_path
        with tarfile.open(tar_target, "w:gz") as tar:
            tar.add(staged_db, arcname=DB_ARCHIVE_NAME)
            tar.add(tmp_path / MANIFEST_NAME, arcname=MANIFEST_NAME)
            if env_included:
                tar.add(tmp_path / ENV_ARCHIVE_NAME, arcname=ENV_ARCHIVE_NAME)

        if recipient is not None:
            pyrage.encrypt_file(str(tar_target), str(archive_path), [recipient])

    try:
        archive_path.chmod(0o600)
    except OSError:
        pass
    return archive_path


def _iter_archives(backup_dir: Path) -> list[Path]:
    """All backup archives (plaintext and encrypted), newest first by name."""
    archives: list[Path] = []
    for pattern in ARCHIVE_GLOBS:
        archives.extend(backup_dir.glob(pattern))
    return sorted(archives, key=lambda p: p.name, reverse=True)


def prune_backups(backup_dir: Path, retention_count: int) -> list[Path]:
    """Delete oldest archives beyond retention_count; return removed paths."""
    if not backup_dir.is_dir():
        return []
    archives = _iter_archives(backup_dir)
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
            "encrypted": archive.name.endswith(ENCRYPTED_ARCHIVE_SUFFIX),
            "reason": reason,
            "pruned": [str(p) for p in removed],
            "retention": cfg.retention_count,
        }
        _append_log(cfg, f"OK reason={reason} archive={archive.name} pruned={len(removed)}")
        _write_audit_sync(
            cfg.db_path, "system", "backup.run", f"{archive.name} reason={reason}"
        )
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
    for archive in _iter_archives(cfg.backup_dir):
        rows.append(
            {
                "archive": str(archive),
                "name": archive.name,
                "size_bytes": archive.stat().st_size,
                "mtime_utc": datetime.fromtimestamp(
                    archive.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "encrypted": archive.name.endswith(ENCRYPTED_ARCHIVE_SUFFIX),
            }
        )
    return rows


def _safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    """Extract archive members only when paths stay inside destination."""
    dest_root = destination.resolve()
    for member in tar.getmembers():
        target_path = (dest_root / member.name).resolve()
        if not target_path.is_relative_to(dest_root):
            raise RuntimeError(f"Unsafe path in archive: {member.name}")
    tar.extractall(dest_root)


def _verify_archive_contents(tmp_path: Path) -> tuple[bool, str]:
    db_file = tmp_path / DB_ARCHIVE_NAME
    if not db_file.is_file():
        return False, "archive missing briefr.db"
    return check_db_integrity(db_file)


def _extract_archive(archive: Path, cfg: BackupConfig, tmp_path: Path) -> None:
    """Decrypt (when *.age) and safely extract an archive into tmp_path."""
    tar_path = archive
    if archive.name.endswith(ENCRYPTED_ARCHIVE_SUFFIX):
        if cfg.age_key_path is None:
            raise RuntimeError(
                "Archive is age-encrypted but no key is configured "
                f"(set BACKUP_AGE_KEY_FILE): {archive.name}"
            )
        identity = load_age_identity(cfg.age_key_path)
        tar_path = tmp_path / "decrypted.tar.gz"
        pyrage.decrypt_file(str(archive), str(tar_path), [identity])
    with tarfile.open(tar_path, "r:gz") as tar:
        _safe_extract_tar(tar, tmp_path)
    if tar_path != archive:
        tar_path.unlink()


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
        _extract_archive(archive, cfg, tmp_path)

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
        "encrypted": archive.name.endswith(ENCRYPTED_ARCHIVE_SUFFIX),
        "db_path": str(cfg.db_path),
        "env_restored": env_restored,
        "integrity": restored_msg,
    }
    _append_log(cfg, f"RESTORE archive={archive.name} db={cfg.db_path}")
    _write_audit_sync(cfg.db_path, "system", "backup.restore", archive.name)
    logger.warning("Database restored from %s", archive)
    return result


def find_latest_valid_backup(config: BackupConfig | None = None) -> Path | None:
    cfg = config or BackupConfig.from_env()
    for entry in list_backups(cfg):
        archive = Path(entry["archive"])
        try:
            with tempfile.TemporaryDirectory(prefix="briefr-verify-") as tmp:
                tmp_path = Path(tmp)
                _extract_archive(archive, cfg, tmp_path)
                ok, _ = _verify_archive_contents(tmp_path)
                if ok:
                    return archive
        except (
            OSError,
            tarfile.TarError,
            RuntimeError,
            pyrage.DecryptError,
            pyrage.IdentityError,
        ):
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
