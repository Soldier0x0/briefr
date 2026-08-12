"""Tests for /api/admin/infra-classifications + /api/admin/threat-intel/status.

The infra-classification store (app.infra_classifications) is Postgres-only
(Alembic 040) — on the default SQLite test path there is no such table. To
exercise the real router logic (validation, status codes, audit), the
db/blocklist.py functions are stubbed at the routers.admin.blocklist import
boundary with in-memory async fakes whose duplicate/missing-row semantics
mirror db/blocklist.py (insert raises ValueError on duplicate host; update/
delete return None/False for a missing row) so the router's own 400/409/404
paths stay real. One PG-gated round-trip test runs against a live Postgres.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from blocklist.infra_seed import (
    _SEED_HOSTS,
    CLASSIFICATIONS,
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
    UNKNOWN,
)
from tests.conftest import _postgres_is_live, run_db_test, seed_pytest_auth_user_if_missing


class FakeInfraStore:
    """In-memory stand-in for app.infra_classifications CRUD with db/blocklist.py semantics."""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    def _copy(self, row_id: int) -> dict:
        return dict(self._rows[row_id])

    async def fetch(self, _db):
        return [self._copy(i) for i in sorted(self._rows)]

    async def insert(
        self,
        _db,
        *,
        host: str,
        classification: str,
        enabled: int = 1,
        provenance: str = "",
        reason: str = "",
        notes: str = "",
    ):
        if any(r["host"] == host for r in self._rows.values()):
            raise ValueError(f"Host already classified: {host}")
        from db.timeutil import utcnow_str

        now = utcnow_str()
        row_id = self._next_id
        self._next_id += 1
        row = {
            "id": row_id,
            "host": host,
            "classification": classification,
            "enabled": enabled,
            "provenance": provenance,
            "reason": reason,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        }
        self._rows[row_id] = row
        return dict(row)

    async def update(
        self,
        _db,
        row_id: int,
        *,
        classification: str | None = None,
        enabled: int | None = None,
        provenance: str | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ):
        if row_id not in self._rows:
            return None
        from db.timeutil import utcnow_str

        row = self._rows[row_id]
        for key, value in (
            ("classification", classification),
            ("enabled", enabled),
            ("provenance", provenance),
            ("reason", reason),
            ("notes", notes),
        ):
            if value is not None:
                row[key] = value
        row["updated_at"] = utcnow_str()
        return dict(row)

    async def delete(self, _db, row_id: int) -> bool:
        if row_id not in self._rows:
            return False
        del self._rows[row_id]
        return True


@pytest.fixture
def infra_store() -> FakeInfraStore:
    return FakeInfraStore()


@pytest.fixture
def admin_client(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "infra.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)
    _rl.admin_read_bucket._buckets.pop("testclient", None)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        yield client


@pytest.fixture
def infra_stubs(admin_client, monkeypatch, infra_store: FakeInfraStore) -> FakeInfraStore:
    """Stub the PG-only db/blocklist.py functions at the router import boundary."""
    monkeypatch.setattr(
        "routers.admin.blocklist.fetch_infra_classifications", infra_store.fetch
    )
    monkeypatch.setattr(
        "routers.admin.blocklist.insert_infra_classification", infra_store.insert
    )
    monkeypatch.setattr(
        "routers.admin.blocklist.update_infra_classification", infra_store.update
    )
    monkeypatch.setattr(
        "routers.admin.blocklist.delete_infra_classification", infra_store.delete
    )
    return infra_store


@pytest.mark.no_auth
def test_unauthenticated_admin_request_returns_401(admin_client):
    admin_client.cookies.clear()
    resp = admin_client.get("/api/admin/infra-classifications")
    assert resp.status_code == 401


def test_non_admin_returns_403(admin_client):
    from auth.tokens import create_access_token

    seed_pytest_auth_user_if_missing(user_id=2, username="pytest-user", role="user")
    admin_client.cookies.set("briefr_at", create_access_token(2, "pytest-user", "user"))
    resp = admin_client.get("/api/admin/infra-classifications")
    assert resp.status_code == 403


def test_create_infra_classification_succeeds(admin_client, infra_stubs):
    resp = admin_client.post(
        "/api/admin/infra-classifications",
        json={
            "host": "attacker.example.com",
            "classification": "TRUSTED_SERVICE",
            "enabled": True,
            "reason": "test fixture",
        },
    )
    assert resp.status_code == 200
    row = resp.json()
    assert row["host"] == "attacker.example.com"
    assert row["classification"] == "TRUSTED_SERVICE"
    assert row["enabled"] == 1
    assert row["provenance"] == "admin"


def test_create_rejects_invalid_host(admin_client, infra_stubs):
    resp = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "notadomain", "classification": "UNKNOWN"},
    )
    assert resp.status_code == 400


def test_create_rejects_invalid_classification(admin_client, infra_stubs):
    resp = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "BOGUS"},
    )
    assert resp.status_code == 400


def test_create_rejects_non_string_classification(admin_client, infra_stubs):
    """A non-string classification (int/bool) must 400, not raise a 500."""
    for bad in (1, True, {"a": 1}, ["UNKNOWN"]):
        resp = admin_client.post(
            "/api/admin/infra-classifications",
            json={"host": "example.com", "classification": bad},
        )
        assert resp.status_code == 400, f"classification={bad!r} must be rejected"


def test_patch_rejects_non_string_classification(admin_client, infra_stubs):
    created = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "UNKNOWN"},
    ).json()
    for bad in (1, True, {"a": 1}):
        resp = admin_client.patch(
            f"/api/admin/infra-classifications/{created['id']}",
            json={"classification": bad},
        )
        assert resp.status_code == 400, f"classification={bad!r} must be rejected"


def test_create_rejects_invalid_enabled(admin_client, infra_stubs):
    resp = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "UNKNOWN", "enabled": "banana"},
    )
    assert resp.status_code == 400


def test_create_duplicate_host_returns_409(admin_client, infra_stubs):
    first = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "UNKNOWN"},
    )
    assert first.status_code == 200
    second = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "TRUSTED_SERVICE"},
    )
    assert second.status_code == 409
    assert "Host already classified" in second.json()["detail"]


def test_patch_existing_updates_fields(admin_client, infra_stubs):
    created = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "UNKNOWN", "reason": "before"},
    ).json()
    resp = admin_client.patch(
        f"/api/admin/infra-classifications/{created['id']}",
        json={"classification": "TRUSTED_SERVICE", "enabled": 0, "reason": "after"},
    )
    assert resp.status_code == 200
    row = resp.json()
    assert row["classification"] == "TRUSTED_SERVICE"
    assert row["enabled"] == 0
    assert row["reason"] == "after"


def test_patch_missing_row_returns_404(admin_client, infra_stubs):
    resp = admin_client.patch(
        "/api/admin/infra-classifications/999",
        json={"classification": "UNKNOWN"},
    )
    assert resp.status_code == 404


def test_patch_invalid_classification_returns_400(admin_client, infra_stubs):
    resp = admin_client.patch(
        "/api/admin/infra-classifications/1",
        json={"classification": "BOGUS"},
    )
    assert resp.status_code == 400


def test_delete_existing_returns_ok(admin_client, infra_stubs):
    created = admin_client.post(
        "/api/admin/infra-classifications",
        json={"host": "example.com", "classification": "UNKNOWN"},
    ).json()
    resp = admin_client.delete(f"/api/admin/infra-classifications/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_delete_missing_returns_404(admin_client, infra_stubs):
    resp = admin_client.delete("/api/admin/infra-classifications/999")
    assert resp.status_code == 404


def test_list_sorted_by_host_and_contains_created(admin_client, infra_stubs):
    for host in ("zulu.example.com", "alpha.example.com", "mike.example.com"):
        resp = admin_client.post(
            "/api/admin/infra-classifications",
            json={"host": host, "classification": "UNKNOWN", "notes": "sorted test"},
        )
        assert resp.status_code == 200
    resp = admin_client.get("/api/admin/infra-classifications")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    hosts = [r["host"] for r in rows]
    assert hosts == ["alpha.example.com", "mike.example.com", "zulu.example.com"]
    assert any(r["classification"] == "UNKNOWN" for r in rows)


def test_threat_intel_status_has_expected_keys(admin_client, monkeypatch):
    async def _fake_build(_db):
        return {
            "meta": {
                "candidate_count": 42,
                "eligible_count": 30,
                "excluded_count": 12,
                "generated_at": "2026-01-01T00:00:00Z",
            },
        }

    monkeypatch.setattr("blocklist.build.build_blocklist", _fake_build)
    resp = admin_client.get("/api/admin/threat-intel/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "token_configured" in data
    assert "rate_limit_per_minute" in data
    assert data["candidate_count"] == 42
    assert data["eligible_count"] == 30
    assert data["excluded_count"] == 12
    assert "publish_urls" in data


def test_seed_hosts_are_valid_classifications():
    assert _SEED_HOSTS, "_SEED_HOSTS must not be empty"
    hosts = [host for host, _, _ in _SEED_HOSTS]
    assert len(hosts) == len(set(hosts)), "seed hosts must be unique"
    assert len(hosts) >= 6
    classifications_used = {classification for _, classification, _ in _SEED_HOSTS}
    assert classifications_used <= set(CLASSIFICATIONS)
    assert LEGITIMATE_DOMAIN in classifications_used
    assert SHARED_LEGITIMATE_INFRASTRUCTURE in classifications_used
    for host, classification, reason in _SEED_HOSTS:
        assert host and "." in host
        assert classification in CLASSIFICATIONS
        assert reason


@pytest.mark.skipif(
    not _postgres_is_live(),
    reason="requires live Postgres (app.infra_classifications is PG-only)",
)
def test_infra_classifications_pg_round_trip():
    async def _run():
        import db.blocklist as dbbl
        from blocklist.infra_seed import seed_infra_classifications
        from database import get_db

        db = await get_db()
        try:
            written = await seed_infra_classifications(db)
            await db.commit()
            assert written == len(_SEED_HOSTS)
            assert await seed_infra_classifications(db) == 0  # idempotent
            await db.commit()

            rows = await dbbl.fetch_infra_classifications(db)
            seeded = {r["host"] for r in rows}
            assert {host for host, _, _ in _SEED_HOSTS} <= seeded

            row = await dbbl.insert_infra_classification(
                db,
                host="pg-roundtrip.example.com",
                classification=UNKNOWN,
                enabled=0,
                reason="test",
            )
            await db.commit()
            assert row["host"] == "pg-roundtrip.example.com"

            with pytest.raises(ValueError):
                await dbbl.insert_infra_classification(
                    db,
                    host="pg-roundtrip.example.com",
                    classification="UNKNOWN",
                    enabled=1,
                )

            updated = await dbbl.update_infra_classification(
                db, row["id"], classification=TRUSTED_SERVICE, enabled=1
            )
            assert updated is not None
            assert updated["classification"] == TRUSTED_SERVICE

            assert await dbbl.delete_infra_classification(db, row["id"]) is True
            await db.commit()
        finally:
            await db.close()

    run_db_test(_run())


@pytest.mark.skipif(
    not _postgres_is_live(),
    reason="requires live Postgres (app.infra_classifications is PG-only)",
)
def test_infra_classifications_pg_seed_is_atomic_under_concurrency():
    """Concurrent seeders on an ISOLATED empty table race safely: exactly one
    writes the full seed and the others write zero.

    Isolated empty seed state is required — the round-trip test above commits
    the complete seed set, and a pre-seeded table would let every concurrent
    seeder return 0 without ever contending (a vacuous pass).
    """

    async def _run():
        import asyncio

        from blocklist.infra_seed import seed_infra_classifications
        from database import get_db

        async def _seed_once() -> int:
            db = await get_db()
            try:
                written = await seed_infra_classifications(db)
                await db.commit()
                return written
            finally:
                await db.close()

        async def _clear_seed() -> None:
            db = await get_db()
            try:
                placeholders = ", ".join("?" for _ in _SEED_HOSTS)
                await db.execute(
                    f"DELETE FROM app.infra_classifications WHERE host IN ({placeholders})",
                    tuple(host for host, _, _ in _SEED_HOSTS),
                )
                await db.commit()
            finally:
                await db.close()

        await _clear_seed()

        results = await asyncio.gather(_seed_once(), _seed_once(), _seed_once())
        assert sorted(results) == [0, 0, len(_SEED_HOSTS)], (
            "exactly one concurrent seeder must write the full seed and the "
            "others must write zero (INSERT .. ON CONFLICT (host) DO NOTHING)"
        )

        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT host FROM app.infra_classifications"
            )
            hosts = {dict(r)["host"] for r in rows}
            assert {host for host, _, _ in _SEED_HOSTS} <= hosts
        finally:
            await db.close()

    run_db_test(_run())


@pytest.mark.skipif(
    not _postgres_is_live(),
    reason="requires live Postgres (app.infra_classifications is PG-only)",
)
def test_infra_classifications_pg_rejects_invalid_writes():
    """Direct SQL writes must respect the migration 040 CHECK constraints —
    invalid classification/enabled values are rejected at the DB layer, not
    just by API validation (which never guards direct SQL writes)."""

    async def _run():
        from db.blocklist import insert_infra_classification, update_infra_classification
        from db.errors import DatabaseError
        from database import get_db

        db = await get_db()
        try:
            # Baseline: valid writes still succeed.
            row = await insert_infra_classification(
                db,
                host="pg-invalid-writes.example.com",
                classification=UNKNOWN,
                enabled=0,
                reason="CHECK constraint test",
            )
            await db.commit()
            assert row["host"] == "pg-invalid-writes.example.com"

            # Invalid classification on INSERT is rejected.
            with pytest.raises(DatabaseError):
                await insert_infra_classification(
                    db,
                    host="pg-invalid-writes-bad.example.com",
                    classification="NOT_A_REAL_CLASSIFICATION",
                    enabled=1,
                )
            await db.rollback()

            # Invalid enabled on INSERT is rejected.
            with pytest.raises(DatabaseError):
                await insert_infra_classification(
                    db,
                    host="pg-invalid-writes-bad2.example.com",
                    classification=UNKNOWN,
                    enabled=5,
                )
            await db.rollback()

            # Invalid classification on UPDATE is rejected.
            with pytest.raises(DatabaseError):
                await update_infra_classification(
                    db, row["id"], classification="NOT_A_REAL_CLASSIFICATION"
                )
            await db.rollback()

            # Invalid enabled on UPDATE is rejected.
            with pytest.raises(DatabaseError):
                await update_infra_classification(db, row["id"], enabled=9)
            await db.rollback()

            # Row is unchanged after the rejected updates.
            rows = await db.execute_fetchall(
                "SELECT id, host, classification, enabled FROM app.infra_classifications"
                " WHERE id = ?",
                (row["id"],),
            )
            intact = dict(rows[0])
            assert intact["classification"] == UNKNOWN
            assert intact["enabled"] == 0

            cursor = await db.execute(
                "DELETE FROM app.infra_classifications WHERE id = ?", (row["id"],)
            )
            assert (getattr(cursor, "rowcount", 0) or 0) > 0
            await db.commit()
        finally:
            await db.close()

    run_db_test(_run())