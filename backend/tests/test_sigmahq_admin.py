"""Admin wiring for SigmaHQ index sync (U2)."""

from __future__ import annotations

from pathlib import Path

from routers.admin.helpers import _job_is_disabled
from routers.admin.jobs import _JOB_RUN_MAP
from scheduler_locks import get_lock


def test_job_run_map_and_lock():
    assert _JOB_RUN_MAP.get("sigmahq_index_sync") == "run_sigmahq_index_sync"
    assert get_lock("sigmahq_index_sync") is not None
    import scheduler as sched

    assert hasattr(sched, "run_sigmahq_index_sync")
    assert callable(sched.run_sigmahq_index_sync)


def test_disabled_gate_default_enabled(monkeypatch):
    monkeypatch.delenv("SIGMAHQ_INDEX_SYNC_ENABLED", raising=False)
    assert _job_is_disabled("sigmahq_index_sync") is False
    monkeypatch.setenv("SIGMAHQ_INDEX_SYNC_ENABLED", "0")
    assert _job_is_disabled("sigmahq_index_sync") is True


def test_catalog_entry_exists():
    catalog = Path(__file__).resolve().parents[2] / "frontend/src/pages/admin/catalog.js"
    text = catalog.read_text(encoding="utf-8")
    assert "sigmahq_index_sync:" in text
    assert "Sync SigmaHQ index" in text


def test_config_schema_keys():
    from config_schema import CONFIG_SCHEMA

    keys = {f.key for f in CONFIG_SCHEMA}
    assert "SIGMAHQ_INDEX_SYNC_ENABLED" in keys
    assert "SIGMAHQ_INDEX_SYNC_INTERVAL_HOURS" in keys


def test_force_resync_handler_exists():
    from routers.admin import feeds as feeds_mod

    assert hasattr(feeds_mod, "force_sigmahq_resync")
    assert callable(feeds_mod.force_sigmahq_resync)
