"""Tests for the audit_log table and its writers (refreshes, backups, restores)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from backup.manager import restore_backup, run_backup
from tests.conftest import run_db_test
from tests.test_backup_manager import _cfg, _corrupt_db, _make_db


def test_write_audit_log_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "audit.db"))

    async def _run():
        await database.init_db()
        db = await database.get_db()
        try:
            await database.write_audit_log(
                db, "operator@example.com", "refresh.full", "nvd+kev+epss"
            )
            await database.write_audit_log(db, None, "refresh.kev", "kev")
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT actor, action, target, created_at FROM audit_log ORDER BY id"
            )
            return [dict(r) for r in rows]
        finally:
            await db.close()

    rows = run_db_test(_run)
    assert rows[0]["actor"] == "operator@example.com"
    assert rows[0]["action"] == "refresh.full"
    assert rows[0]["target"] == "nvd+kev+epss"
    assert rows[0]["created_at"]
    assert rows[1]["actor"] == ""  # no identity until built-in app login ships


def test_backup_run_writes_audit_row(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)

    result = run_backup(reason="test", config=cfg)
    assert result["status"] == "ok"

    conn = sqlite3.connect(cfg.db_path)
    try:
        rows = conn.execute(
            "SELECT actor, action, target FROM audit_log"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    actor, action, target = rows[0]
    assert actor == "system"
    assert action == "backup.run"
    assert Path(result["archive"]).name in target
    assert "reason=test" in target


def test_restore_writes_audit_row(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    archive = Path(run_backup(reason="seed", config=cfg)["archive"])
    _corrupt_db(cfg.db_path)

    result = restore_backup(archive, config=cfg, force=True)
    assert result["status"] == "ok"

    conn = sqlite3.connect(cfg.db_path)
    try:
        rows = conn.execute(
            "SELECT actor, action, target FROM audit_log WHERE action = 'backup.restore'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("system", "backup.restore", archive.name)]
