"""Tests for age-encrypted backup archives (§5.6): keygen, round-trip,
startup auto-restore, retention with mixed archives, and key-location guard."""

import json
import sqlite3
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from backup.manager import (
    BackupConfig,
    check_db_integrity,
    ensure_db_or_restore,
    find_latest_valid_backup,
    generate_age_key,
    list_backups,
    load_age_identity,
    prune_backups,
    restore_backup,
    run_backup,
)

AGE_HEADER = b"age-encryption.org/v1"


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


def _row_names(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [row[0] for row in conn.execute("SELECT name FROM items ORDER BY id")]
    finally:
        conn.close()


def _cfg(tmp_path: Path, *, key_path: Path | None) -> BackupConfig:
    db_path = tmp_path / "briefr.db"
    env_path = tmp_path / ".env"
    env_path.write_text("DB_PATH=briefr.db\n", encoding="utf-8")
    return BackupConfig(
        db_path=db_path,
        env_path=env_path,
        backup_dir=tmp_path / "backups",
        retention_count=3,
        log_path=tmp_path / "backups" / "logs" / "backup.log",
        enabled=True,
        age_key_path=key_path,
    )


@pytest.fixture
def key_file(tmp_path) -> Path:
    key_path = tmp_path / "keys" / "backup-age.key"
    generate_age_key(key_path)
    return key_path


def test_generate_age_key_permissions_and_format(tmp_path):
    key_path = tmp_path / "keys" / "backup-age.key"
    public_key = generate_age_key(key_path)

    assert public_key.startswith("age1")
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert key_path.parent.stat().st_mode & 0o777 == 0o700
    body = key_path.read_text(encoding="utf-8")
    assert f"# public key: {public_key}" in body
    assert "AGE-SECRET-KEY-" in body

    identity = load_age_identity(key_path)
    assert str(identity.to_public()) == public_key

    with pytest.raises(FileExistsError):
        generate_age_key(key_path)


def test_generate_age_key_leaves_existing_parent_mode_alone(tmp_path, monkeypatch):
    existing = tmp_path / "shared"
    existing.mkdir(mode=0o755)
    generate_age_key(existing / "backup-age.key")
    assert existing.stat().st_mode & 0o777 == 0o755

    # Relative path: must never chmod the current working directory
    monkeypatch.chdir(existing)
    cwd_mode_before = existing.stat().st_mode & 0o777
    generate_age_key(Path("relative-age.key"))
    assert existing.stat().st_mode & 0o777 == cwd_mode_before
    assert (existing / "relative-age.key").stat().st_mode & 0o777 == 0o600


def test_load_age_identity_rejects_missing_or_empty(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_age_identity(tmp_path / "nope.key")

    empty = tmp_path / "empty.key"
    empty.write_text("# only comments\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="No AGE-SECRET-KEY"):
        load_age_identity(empty)


def test_run_backup_produces_age_encrypted_archive(tmp_path, key_file):
    cfg = _cfg(tmp_path, key_path=key_file)
    _make_db(cfg.db_path)

    result = run_backup(reason="test", config=cfg)
    assert result["status"] == "ok"
    assert result["encrypted"] is True

    archive = Path(result["archive"])
    assert archive.name.endswith(".tar.gz.age")
    assert archive.stat().st_mode & 0o777 == 0o600
    # age binary format starts with an ASCII header; gzip starts with \x1f\x8b
    assert archive.read_bytes()[: len(AGE_HEADER)] == AGE_HEADER
    with pytest.raises(tarfile.ReadError):
        tarfile.open(archive, "r:gz").close()


def test_encrypted_backup_restore_round_trip(tmp_path, key_file):
    cfg = _cfg(tmp_path, key_path=key_file)
    _make_db(cfg.db_path)
    archive = Path(run_backup(reason="seed", config=cfg)["archive"])

    _corrupt_db(cfg.db_path)
    assert check_db_integrity(cfg.db_path)[0] is False

    result = restore_backup(archive, config=cfg, force=True)
    assert result["status"] == "ok"
    assert result["encrypted"] is True
    assert check_db_integrity(cfg.db_path)[0] is True
    assert _row_names(cfg.db_path) == ["alpha"]
    # .env travelled inside the encrypted archive and came back
    assert result["env_restored"] is True


def test_startup_auto_restore_from_encrypted_archive(tmp_path, key_file):
    cfg = _cfg(tmp_path, key_path=key_file)
    _make_db(cfg.db_path)
    run_backup(reason="seed", config=cfg)

    _corrupt_db(cfg.db_path)
    result = ensure_db_or_restore(config=cfg)
    assert result["status"] == "restored"
    assert check_db_integrity(cfg.db_path)[0] is True
    assert _row_names(cfg.db_path) == ["alpha"]


def test_restore_encrypted_archive_without_key_fails(tmp_path, key_file):
    cfg = _cfg(tmp_path, key_path=key_file)
    _make_db(cfg.db_path)
    archive = Path(run_backup(reason="seed", config=cfg)["archive"])

    keyless = _cfg(tmp_path, key_path=None)
    with pytest.raises(RuntimeError, match="no key is configured"):
        restore_backup(archive, config=keyless, force=True)


def test_find_latest_valid_backup_skips_undecryptable(tmp_path, key_file):
    cfg = _cfg(tmp_path, key_path=key_file)
    _make_db(cfg.db_path)
    plain_cfg = _cfg(tmp_path, key_path=None)
    plain = Path(run_backup(reason="plain", config=plain_cfg)["archive"])
    encrypted = Path(run_backup(reason="enc", config=cfg)["archive"])

    # With the key: the newer encrypted archive wins
    assert find_latest_valid_backup(cfg) == encrypted
    # Wrong key: encrypted archive skipped, falls back to plaintext one
    other_key = tmp_path / "keys" / "other.key"
    generate_age_key(other_key)
    wrong = _cfg(tmp_path, key_path=other_key)
    assert find_latest_valid_backup(wrong) == plain


def test_list_and_prune_handle_mixed_archives(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    names = [
        "briefr-20260101T000000Z.tar.gz",
        "briefr-20260102T000000Z.tar.gz",
        "briefr-20260103T000000Z.tar.gz.age",
        "briefr-20260104T000000Z.tar.gz.age",
    ]
    for name in names:
        (backup_dir / name).write_bytes(b"x")

    cfg = BackupConfig(
        db_path=tmp_path / "briefr.db",
        env_path=None,
        backup_dir=backup_dir,
        enabled=True,
    )
    rows = list_backups(cfg)
    assert [row["name"] for row in rows] == list(reversed(names))
    assert [row["encrypted"] for row in rows] == [True, True, False, False]

    removed = prune_backups(backup_dir, retention_count=2)
    assert sorted(p.name for p in removed) == names[:2]
    assert sorted(p.name for p in backup_dir.iterdir()) == names[2:]


def test_backup_refuses_key_inside_backup_dir(tmp_path):
    cfg = _cfg(tmp_path, key_path=None)
    key_inside = cfg.backup_dir / "backup-age.key"
    cfg.backup_dir.mkdir(parents=True, exist_ok=True)
    generate_age_key(key_inside)
    bad_cfg = _cfg(tmp_path, key_path=key_inside)
    _make_db(bad_cfg.db_path)

    with pytest.raises(RuntimeError, match="outside BACKUP_DIR"):
        run_backup(reason="test", config=bad_cfg)


def test_backup_fails_loudly_when_configured_key_missing(tmp_path):
    cfg = _cfg(tmp_path, key_path=tmp_path / "keys" / "missing.key")
    _make_db(cfg.db_path)
    with pytest.raises(FileNotFoundError, match="age key file not found"):
        run_backup(reason="test", config=cfg)


def test_from_env_age_key_resolution(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    explicit = tmp_path / "keys" / "backup-age.key"
    monkeypatch.setenv("BACKUP_AGE_KEY_FILE", str(explicit))
    cfg = BackupConfig.from_env(backend_dir=backend_dir)
    # Explicit path kept even though the file does not exist yet (fail loudly)
    assert cfg.age_key_path == explicit

    monkeypatch.setenv("BACKUP_AGE_KEY_FILE", "")
    cfg = BackupConfig.from_env(backend_dir=backend_dir)
    assert cfg.age_key_path is None

    # Unset: production default only applies when that file exists
    monkeypatch.delenv("BACKUP_AGE_KEY_FILE", raising=False)
    cfg = BackupConfig.from_env(backend_dir=backend_dir)
    assert cfg.age_key_path is None or cfg.age_key_path.is_file()


def test_unencrypted_backups_still_work_without_key(tmp_path):
    cfg = _cfg(tmp_path, key_path=None)
    _make_db(cfg.db_path)
    result = run_backup(reason="test", config=cfg)
    assert result["encrypted"] is False
    archive = Path(result["archive"])
    assert archive.name.endswith(".tar.gz")
    with tarfile.open(archive, "r:gz") as tar:
        manifest = json.loads(tar.extractfile("manifest.json").read().decode("utf-8"))
    assert manifest["encrypted"] is False
    assert manifest["age_public_key"] is None
