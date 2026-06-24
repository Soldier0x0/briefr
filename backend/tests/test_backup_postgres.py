"""Tests for PostgreSQL backup path (pg_dump archives)."""

import json
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from backup.manager import (
    BackupConfig,
    _archive_backend,
    restore_backup,
    run_backup,
)
from backup.postgres_util import (
    PG_DUMP_ARCHIVE_NAME,
    PGDUMP_MAGIC,
    parse_postgres_url,
    redact_database_url,
    verify_pg_dump,
)


def _pg_cfg(tmp_path: Path) -> BackupConfig:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "DATABASE_URL=postgresql://briefr:secret@127.0.0.1:5432/briefr\n",
        encoding="utf-8",
    )
    return BackupConfig(
        db_path=tmp_path / "briefr.db",
        env_path=env_path,
        backup_dir=tmp_path / "backups",
        retention_count=3,
        log_path=tmp_path / "backups" / "logs" / "backup.log",
        enabled=True,
        database_url="postgresql://briefr:secret@127.0.0.1:5432/briefr",
    )


def _fake_pgdump(_url: str, dest: Path) -> None:
    dest.write_bytes(PGDUMP_MAGIC + b"\x00" * 64)


def test_redact_database_url():
    url = "postgresql://briefr:secret@127.0.0.1:5432/briefr"
    assert redact_database_url(url) == "postgresql://briefr:***@127.0.0.1:5432/briefr"


def test_parse_postgres_url():
    params = parse_postgres_url("postgresql://user:pass@db.example:5433/mydb")
    assert params["host"] == "db.example"
    assert params["port"] == 5433
    assert params["user"] == "user"
    assert params["password"] == "pass"
    assert params["dbname"] == "mydb"


def test_verify_pg_dump_ok_and_bad(tmp_path):
    good = tmp_path / "good.dump"
    good.write_bytes(PGDUMP_MAGIC + b"rest")
    ok, msg = verify_pg_dump(good)
    assert ok is True
    assert msg == "ok"

    bad = tmp_path / "bad.dump"
    bad.write_bytes(b"not-a-dump")
    bad_ok, bad_msg = verify_pg_dump(bad)
    assert bad_ok is False
    assert "not a PostgreSQL" in bad_msg


def test_run_postgres_backup_creates_archive(tmp_path, monkeypatch):
    cfg = _pg_cfg(tmp_path)
    monkeypatch.setattr("backup.manager.run_pg_dump", _fake_pgdump)
    monkeypatch.setattr(
        "backup.manager.check_postgres_health", lambda _url: (True, "ok")
    )
    monkeypatch.setattr("backup.manager.write_audit_postgres", lambda *a, **k: None)

    result = run_backup(reason="test-pg", config=cfg)
    assert result["status"] == "ok"
    archive = Path(result["archive"])
    assert archive.is_file()

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert PG_DUMP_ARCHIVE_NAME in names
    assert "manifest.json" in names
    assert ".env" in names

    manifest = json.loads(
        tarfile.open(archive, "r:gz").extractfile("manifest.json").read()
    )
    assert manifest["backend"] == "postgresql"
    assert manifest["version"] == 2
    assert "***" in manifest["source_db"]


def test_archive_backend_detects_postgres_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"backend": "postgresql"}),
        encoding="utf-8",
    )
    assert _archive_backend(tmp_path) == "postgresql"


def test_restore_postgres_archive(tmp_path, monkeypatch):
    cfg = _pg_cfg(tmp_path)
    monkeypatch.setattr("backup.manager.run_pg_dump", _fake_pgdump)
    monkeypatch.setattr(
        "backup.manager.check_postgres_health", lambda _url: (True, "ok")
    )
    monkeypatch.setattr("backup.manager.write_audit_postgres", lambda *a, **k: None)

    archive_path = Path(run_backup(reason="seed", config=cfg)["archive"])
    restore_calls: list[Path] = []

    def fake_restore(url: str, dump_path: Path) -> None:
        assert "postgresql://" in url
        restore_calls.append(dump_path)
        ok, _ = verify_pg_dump(dump_path)
        assert ok

    monkeypatch.setattr("backup.manager.run_pg_restore", fake_restore)

    result = restore_backup(archive_path, config=cfg, force=True)
    assert result["status"] == "ok"
    assert result["backend"] == "postgresql"
    assert len(restore_calls) == 1


def test_run_postgres_backup_refuses_unreachable_db(tmp_path, monkeypatch):
    cfg = _pg_cfg(tmp_path)
    monkeypatch.setattr(
        "backup.manager.check_postgres_health",
        lambda _url: (False, "connection refused"),
    )
    with pytest.raises(RuntimeError, match="Refusing to backup unreachable"):
        run_backup(reason="test", config=cfg)


def test_run_postgres_backup_requires_pg_dump(tmp_path, monkeypatch):
    cfg = _pg_cfg(tmp_path)
    monkeypatch.setattr(
        "backup.manager.check_postgres_health", lambda _url: (True, "ok")
    )

    def boom(_url, _dest):
        raise RuntimeError("pg_dump not found on PATH")

    monkeypatch.setattr("backup.manager.run_pg_dump", boom)
    with pytest.raises(RuntimeError, match="pg_dump not found"):
        run_backup(reason="test", config=cfg)
