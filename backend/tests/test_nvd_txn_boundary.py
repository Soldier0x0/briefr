"""NVD ingest must not hold cves locks across outbound source HTTP.

RCA class: CIRCL/Sploitus latency (DNS hangs, 25s timeouts) inside the NVD
upsert transaction caused concurrent VulnCheck/KEV UPDATEs to hit asyncpg
command_timeout (60s). Commit boundaries separate DB work from source I/O.
Per-source HTTP timeouts must not share the global SQL command_timeout.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_nvd_sync_commits_before_extended_enrich(monkeypatch):
    import scheduler as sched

    order: list[str] = []
    connections: list[object] = []

    class FakeDb:
        async def commit(self):
            order.append("commit")

        async def rollback(self):
            order.append("rollback")

        async def close(self):
            order.append("close")

    async def fake_get_db():
        db = FakeDb()
        connections.append(db)
        order.append("get_db")
        return db

    async def fake_get_watermark(_db):
        return "2026-07-01T00:00:00"

    async def fake_resolve_watermark(_db):
        return "2026-07-01T00:00:00"

    async def fake_fetch_nvd(*_a, **_k):
        return (
            [{"cve_id": "CVE-2026-1", "modified": "2026-07-21T00:00:00"}],
            "2026-07-21T01:00:00",
            True,
            [],
        )

    async def fake_purge(*_a, **_k):
        order.append("purge")
        return 0

    async def fake_delete(*_a, **_k):
        order.append("delete")
        return 0

    async def fake_upsert(*_a, **_k):
        order.append("upsert")

    async def fake_set_wm(*_a, **_k):
        order.append("watermark")

    async def fake_strip(*_a, **_k):
        order.append("strip")
        return 0

    async def fake_fill(*_a, **_k):
        order.append("fill")
        return 0

    async def fake_poc(*_a, **_k):
        order.append("poc")
        return 0

    async def fake_enrich(*_a, **_k):
        order.append("enrich")
        return {"sploitus": 0, "circl": 0}

    monkeypatch.setattr(sched, "get_db", fake_get_db)
    monkeypatch.setattr(sched, "get_nvd_sync_watermark", fake_get_watermark)
    monkeypatch.setattr(sched, "resolve_nvd_watermark", fake_resolve_watermark)
    monkeypatch.setattr(sched, "fetch_nvd_cve_updates", fake_fetch_nvd)
    monkeypatch.setattr(sched, "purge_legacy_rejected_cves", fake_purge)
    monkeypatch.setattr(sched, "delete_cves_by_ids", fake_delete)
    monkeypatch.setattr(sched, "upsert_cves", fake_upsert)
    monkeypatch.setattr(sched, "set_nvd_sync_watermark", fake_set_wm)
    monkeypatch.setattr(sched, "strip_auto_generated_summaries", fake_strip)
    monkeypatch.setattr(sched, "backfill_display_fields", fake_fill)
    monkeypatch.setattr(sched, "backfill_has_poc", fake_poc)
    monkeypatch.setattr(sched, "embeddings_auto_on_ingest_enabled", lambda: False)

    monkeypatch.setattr(
        "feeds.extended.enrich_cves_extended",
        fake_enrich,
        raising=False,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "feeds.extended",
        SimpleNamespace(enrich_cves_extended=fake_enrich),
    )

    await sched._run_nvd_incremental_sync()

    assert "upsert" in order
    assert "enrich" in order
    assert "commit" in order
    assert order.index("commit") < order.index("enrich"), (
        f"ingest must commit before CIRCL/Sploitus enrich; order={order}"
    )
    # Ingest connection must be closed before enrich re-acquires a pool slot.
    assert order.index("close") < order.index("enrich"), (
        f"ingest must release pool before enrich; order={order}"
    )
    assert len(connections) >= 2, "enrich must use a fresh connection after ingest close"


@pytest.mark.asyncio
async def test_enrich_cves_extended_commits_after_each_source_lookup(monkeypatch):
    import feeds.extended as ext

    commits = {"n": 0}

    class FakeDb:
        async def execute_fetchall(self, *_a, **_k):
            return [
                {"cve_id": "CVE-2026-1", "has_poc": 1, "is_kev": 0},
                {"cve_id": "CVE-2026-2", "has_poc": 0, "is_kev": 1},
            ]

        async def commit(self):
            commits["n"] += 1

    async def fake_missing(_db, limit=40):
        return []

    async def fake_sploitus(_db, cve_id):
        return []

    import database as database_mod

    monkeypatch.setattr(database_mod, "get_cve_ids_missing_circl_capec", fake_missing)
    monkeypatch.setattr(ext, "load_sploitus_exploits_for_cve", fake_sploitus)

    stats = await ext.enrich_cves_extended(
        FakeDb(),
        ["CVE-2026-1", "CVE-2026-2"],
        max_per_run=40,
    )
    assert stats["sploitus"] == 2
    assert commits["n"] >= 2, f"expected per-lookup commits, got {commits['n']}"


@pytest.mark.asyncio
async def test_load_circl_commits_before_outbound_http(monkeypatch):
    """CIRCL HTTP timeout must not nest inside an open write transaction."""
    import feeds.extended as ext

    order: list[str] = []

    class FakeDb:
        async def commit(self):
            order.append("commit")

    async def fake_get_cache(*_a, **_k):
        return None

    async def fake_set_cache(*_a, **_k):
        order.append("set_cache")

    async def fake_fetch(cve_id):
        order.append("http")
        assert "commit" in order
        return {"references": [], "capec": []}

    import database as database_mod

    monkeypatch.setattr(database_mod, "get_feed_cache", fake_get_cache)
    monkeypatch.setattr(database_mod, "set_feed_cache", fake_set_cache)
    monkeypatch.setattr(ext, "fetch_circl_cve", fake_fetch)

    result = await ext.load_circl_for_cve(FakeDb(), "CVE-2026-99")
    assert result is not None
    assert order.index("commit") < order.index("http"), order
    assert "set_cache" in order


@pytest.mark.asyncio
async def test_load_sploitus_commits_before_outbound_http(monkeypatch):
    import feeds.extended as ext

    order: list[str] = []

    class FakeDb:
        async def commit(self):
            order.append("commit")

    async def fake_cached(*_a, **_k):
        return None

    async def fake_table(*_a, **_k):
        return None

    async def fake_store(*_a, **_k):
        order.append("store")

    async def fake_fetch(cve_id, limit=25):
        order.append("http")
        assert "commit" in order
        return [{"title": "x", "type": "poc", "source": "sploitus", "url": "https://x"}]

    import database as database_mod

    monkeypatch.setattr(database_mod, "get_cached_cve_exploits", fake_cached)
    monkeypatch.setattr(database_mod, "read_cve_exploits_from_db", fake_table)
    monkeypatch.setattr(database_mod, "store_cve_exploits", fake_store)
    monkeypatch.setattr(ext, "fetch_sploitus_exploits", fake_fetch)

    rows = await ext.load_sploitus_exploits_for_cve(FakeDb(), "CVE-2026-98")
    assert len(rows) == 1
    assert order.index("commit") < order.index("http"), order
