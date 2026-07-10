"""Tests for backup manager integrity, retention, and restore."""

import io
import json
import os
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from db.errors import DatabaseLockedError

from backup.manager import (
    BackupConfig,
    _safe_tar_extractall,
    check_db_integrity,
    ensure_db_or_restore,
    prune_backups,
    restore_backup,
    rotate_log_file,
    run_backup,
)


def _make_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items (name) VALUES ('alpha')")
        conn.commit()
    finally:
        conn.close()


def _corrupt_db(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.truncate(128)


def _cfg(tmp_path: Path, db_name: str = "briefr.db") -> BackupConfig:
    db_path = tmp_path / db_name
    env_path = tmp_path / ".env"
    env_path.write_text("DB_PATH=briefr.db\n", encoding="utf-8")
    return BackupConfig(
        db_path=db_path,
        env_path=env_path,
        backup_dir=tmp_path / "backups",
        retention_count=3,
        log_path=tmp_path / "backups" / "logs" / "backup.log",
        log_max_bytes=200,
        log_backup_count=2,
        enabled=True,
    )


def test_from_env_loads_dotenv(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    custom_db = "data/custom.db"
    custom_backup = tmp_path / "custom-backups"
    (backend_dir / ".env").write_text(
        f"DB_PATH={custom_db}\nBACKUP_DIR={custom_backup}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    cfg = BackupConfig.from_env(backend_dir=backend_dir)
    assert cfg.db_path == (backend_dir / custom_db).resolve()
    assert cfg.backup_dir == custom_backup.resolve()


def test_from_env_respects_existing_env_over_dotenv(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / ".env").write_text("DB_PATH=from-dotenv.db\n", encoding="utf-8")
    override_db = tmp_path / "from-env.db"
    monkeypatch.setenv("DB_PATH", str(override_db))

    cfg = BackupConfig.from_env(backend_dir=backend_dir)
    assert cfg.db_path == override_db.resolve()


def test_check_db_integrity_raises_on_transient_sqlite_error(tmp_path, monkeypatch):
    db = tmp_path / "locked.db"
    _make_db(db)

    def fake_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(sqlite3, "connect", fake_connect)
    with pytest.raises(DatabaseLockedError, match="locked"):
        check_db_integrity(db)


def test_check_db_integrity_ok_and_corrupt(tmp_path):
    db = tmp_path / "ok.db"
    _make_db(db)
    ok, msg = check_db_integrity(db)
    assert ok is True
    assert msg.lower() == "ok"

    bad = tmp_path / "bad.db"
    _make_db(bad)
    _corrupt_db(bad)
    bad_ok, bad_msg = check_db_integrity(bad)
    assert bad_ok is False
    assert bad_msg


def test_run_backup_creates_verified_archive(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)

    result = run_backup(reason="test", config=cfg)
    assert result["status"] == "ok"
    archive = Path(result["archive"])
    assert archive.is_file()
    assert archive.stat().st_mode & 0o777 == 0o600
    assert cfg.backup_dir.stat().st_mode & 0o777 == 0o750

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert "briefr.db" in names
    assert "manifest.json" in names
    assert ".env" in names


def test_run_backup_refuses_corrupt_source(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    _corrupt_db(cfg.db_path)
    with pytest.raises(RuntimeError, match="Refusing to backup corrupt"):
        run_backup(reason="test", config=cfg)


def test_run_backup_interval_guard_skips_recent(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    first = run_backup(reason="scheduled", config=cfg)
    assert first["status"] == "ok"
    second = run_backup(reason="scheduled", config=cfg)
    assert second["status"] == "skipped"
    assert "interval_guard" in second["reason"]


def test_run_backup_interval_guard_allows_manual(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    run_backup(reason="scheduled", config=cfg)
    manual = run_backup(reason="manual-admin", config=cfg)
    assert manual["status"] == "ok"


def test_prune_backups_keeps_newest(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for idx in range(5):
        path = backup_dir / f"briefr-2026010{idx}T000000Z.tar.gz"
        path.write_bytes(b"x")
    removed = prune_backups(backup_dir, retention_count=3)
    assert len(removed) == 2
    assert len(list(backup_dir.glob("briefr-*.tar.gz"))) == 3


def test_prune_backups_uses_filename_not_mtime(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    older = backup_dir / "briefr-20260101T000000Z.tar.gz"
    newer = backup_dir / "briefr-20260102T000000Z.tar.gz"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    now = time.time()
    os.utime(older, (now + 100, now + 100))
    os.utime(newer, (now, now))

    removed = prune_backups(backup_dir, retention_count=1)
    assert removed == [older]
    assert newer.is_file()


def test_restore_rejects_unsafe_tar_paths(tmp_path):
    cfg = _cfg(tmp_path)
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(name="../../escape.txt")
        info.size = 4
        tar.addfile(info, io.BytesIO(b"evil"))

    with pytest.raises(RuntimeError, match="Unsafe path in archive"):
        restore_backup(archive, config=cfg, force=True)


def test_restore_from_backup_replaces_corrupt_db(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    good = run_backup(reason="seed", config=cfg)["archive"]

    _corrupt_db(cfg.db_path)
    corrupt_ok, _ = check_db_integrity(cfg.db_path)
    assert corrupt_ok is False

    result = restore_backup(Path(good), config=cfg, force=True)
    assert result["status"] == "ok"
    restored_ok, _ = check_db_integrity(cfg.db_path)
    assert restored_ok is True


def test_ensure_db_or_restore_auto_recovers(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    archive = run_backup(reason="seed", config=cfg)["archive"]
    assert Path(archive).is_file()

    _corrupt_db(cfg.db_path)
    monkeypatch.setenv("BACKUP_DIR", str(cfg.backup_dir))
    monkeypatch.setenv("DB_PATH", str(cfg.db_path))
    monkeypatch.setenv("ENV_FILE", str(cfg.env_path))

    result = ensure_db_or_restore(config=cfg)
    assert result["status"] == "restored"
    ok, _ = check_db_integrity(cfg.db_path)
    assert ok is True


def test_safe_tar_extractall_rejects_path_traversal(tmp_path):
    malicious = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("pwned", encoding="utf-8")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../payload.txt")
        info.size = payload.stat().st_size
        with payload.open("rb") as handle:
            tar.addfile(info, handle)
    malicious.write_bytes(buf.getvalue())

    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    with tarfile.open(malicious, "r:gz") as tar:
        with pytest.raises(
            (PermissionError, tarfile.OutsideDestinationError),
            match=r"directory traversal|outside the destination",
        ):
            _safe_tar_extractall(tar, extract_dir)


def test_rotate_log_file(tmp_path):
    log_path = tmp_path / "backup.log"
    log_path.write_text("x" * 250, encoding="utf-8")
    rotate_log_file(log_path, max_bytes=100, backup_count=2)
    assert log_path.stat().st_size == 0
    assert log_path.with_suffix(".log.1.gz").is_file()
