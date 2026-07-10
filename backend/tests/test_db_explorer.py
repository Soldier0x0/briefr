"""Security and behavior tests for read-only DB explorer."""

import os

# Conftest's session-scoped Postgres bootstrap reads os.environ only — clear
# DATABASE_URL before collection so these SQLite-isolated tests do not require
# a live Postgres instance when backend/.env points at production DSN.
os.environ["DATABASE_URL"] = ""
os.environ["BRIEFR_REQUIRE_POSTGRES"] = "0"

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from db.explorer_registry import TABLE_REGISTRY
from tests.conftest import run_db_test, seed_pytest_auth_user_if_missing


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    from settings import settings as _settings

    db_path = tmp_path / "explorer.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    sqlite_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setattr("db.config.resolve_database_url", lambda: sqlite_url)
    monkeypatch.setattr("main.resolve_database_url", lambda: sqlite_url)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)

    async def _noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    async def _noop_migrations() -> None:
        return None

    monkeypatch.setattr("database.run_postgres_migrations", _noop_migrations)
    monkeypatch.setattr("main.run_postgres_migrations", _noop_migrations)

    import main as _main_mod
    import database as _database_mod

    _main_mod.is_postgres = lambda url=None: False
    _main_mod.run_postgres_migrations = _noop_migrations
    _database_mod.run_postgres_migrations = _noop_migrations

    import rate_limit as _rl

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.refresh_bucket._buckets.pop("testclient", None)
    _rl.db_explorer_bucket._buckets.pop("testclient", None)

    from database import init_db
    from auth.tokens import create_access_token

    run_db_test(init_db())
    seed_pytest_auth_user_if_missing()
    token = create_access_token(1, "pytest-admin", "admin")

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", token)
        yield client


def _seed_cve(client: TestClient, cve_id: str = "CVE-2024-0001") -> None:
    import database as db_mod

    async def _insert():
        conn = await db_mod.get_db()
        try:
            await conn.execute(
                """
                INSERT INTO cves (cve_id, description, published, modified, severity)
                VALUES (?, 'Test CVE', '2024-01-01', '2024-01-02', 'HIGH')
                """,
                (cve_id,),
            )
            await conn.commit()
        finally:
            await conn.close()

    run_db_test(_insert())


def test_tables_lists_allowlist_only(admin_client):
    resp = admin_client.get("/api/admin/db-explorer/tables")
    assert resp.status_code == 200
    data = resp.json()
    assert data["read_only"] is True
    names = {t["name"] for t in data["tables"]}
    assert names == set(TABLE_REGISTRY.keys())
    assert "users" not in names
    assert "sessions" not in names
    assert "webhook_destinations" not in names
    cves = next(t for t in data["tables"] if t["name"] == "cves")
    assert cves["required_filter"] == "cve_id"
    assert "cve_id" in cves["filter_columns"]


@pytest.mark.parametrize(
    "table_name",
    [
        "users",
        "sessions",
        "app_settings",
        "sync_state",
        "ioc_cache",
        "hunt_packs",
        "webhook_destinations",
        "alembic_version",
        "not_a_table",
        "cves;drop",
        "../users",
    ],
)
def test_forbidden_tables_return_404(admin_client, table_name):
    resp = admin_client.get(f"/api/admin/db-explorer/tables/{table_name}/rows")
    assert resp.status_code == 404


def test_cves_requires_filter(admin_client):
    _seed_cve(admin_client)
    resp = admin_client.get("/api/admin/db-explorer/tables/cves/rows")
    assert resp.status_code == 400
    assert "requires" in resp.json()["detail"].lower()


def test_cves_filter_returns_row(admin_client):
    _seed_cve(admin_client, "CVE-2024-4242")
    resp = admin_client.get(
        "/api/admin/db-explorer/tables/cves/rows",
        params={"filter_column": "cve_id", "filter_value": "CVE-2024-4242"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["rows"][0]["cve_id"] == "CVE-2024-4242"


def test_invalid_cve_filter_rejected(admin_client):
    resp = admin_client.get(
        "/api/admin/db-explorer/tables/cves/rows",
        params={"filter_column": "cve_id", "filter_value": "not-a-cve"},
    )
    assert resp.status_code == 400


def test_sql_injection_filter_column_rejected(admin_client):
    resp = admin_client.get(
        "/api/admin/db-explorer/tables/kev_deadlines/rows",
        params={"filter_column": "cve_id;drop table cves", "filter_value": "CVE-2024-0001"},
    )
    assert resp.status_code == 400


def test_pagination_cap_enforced(admin_client):
    resp = admin_client.get(
        "/api/admin/db-explorer/tables/epss_history/rows",
        params={"limit": 500},
    )
    assert resp.status_code == 422


def test_audit_log_masks_target(admin_client):
    import database as db_mod

    async def _seed():
        conn = await db_mod.get_db()
        try:
            await conn.execute(
                """
                INSERT INTO audit_log (actor, action, target)
                VALUES ('admin', 'config.write', 'https://discord.com/api/webhooks/secret-token-here')
                """
            )
            await conn.commit()
        finally:
            await conn.close()

    run_db_test(_seed())

    resp = admin_client.get("/api/admin/db-explorer/tables/audit_log/rows")
    assert resp.status_code == 200
    row = resp.json()["rows"][0]
    assert "secret-token" not in str(row.get("target", ""))
    assert row["target"] in ("[redacted]", "[redacted-url]", row["target"])


def test_webhook_delivery_log_redacts_error(admin_client):
    import database as db_mod

    async def _seed():
        conn = await db_mod.get_db()
        try:
            await conn.execute(
                """
                INSERT INTO webhook_delivery_log
                    (destination_id, event_type, status, error)
                VALUES ('discord-abc', 'kev.new', 'failed',
                        'HTTP 401 https://discord.com/api/webhooks/abc/TOKEN123')
                """
            )
            await conn.commit()
        finally:
            await conn.close()

    run_db_test(_seed())

    resp = admin_client.get("/api/admin/db-explorer/tables/webhook_delivery_log/rows")
    assert resp.status_code == 200
    err = resp.json()["rows"][0]["error"]
    assert "TOKEN123" not in str(err)
    assert "discord.com" not in str(err) or "[redacted" in str(err)


def test_unauthenticated_returns_401(tmp_path, monkeypatch):
    from settings import settings as _settings

    db_path = tmp_path / "explorer-unauth.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    sqlite_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setattr("db.config.resolve_database_url", lambda: sqlite_url)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)
    monkeypatch.setattr("main.is_postgres", lambda url=None: False)

    async def _noop_migrations() -> None:
        return None

    monkeypatch.setattr("database.run_postgres_migrations", _noop_migrations)
    monkeypatch.setattr("main.run_postgres_migrations", _noop_migrations)
    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    async def _noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/admin/db-explorer/tables")
    assert resp.status_code == 401


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="audit log read test uses SQLite seed path",
)
def test_browse_writes_audit_entry(admin_client):
    _seed_cve(admin_client, "CVE-2024-9999")
    browse = admin_client.get(
        "/api/admin/db-explorer/tables/cves/rows",
        params={"filter_column": "cve_id", "filter_value": "CVE-2024-9999"},
    )
    assert browse.status_code == 200

    audit = admin_client.get("/api/admin/audit-log?limit=20")
    assert audit.status_code == 200
    actions = [r["action"] for r in audit.json().get("rows", [])]
    assert "db.explorer.browse.cves" in actions
