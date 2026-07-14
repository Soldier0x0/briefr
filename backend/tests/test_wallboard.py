"""Tests for GET /api/wallboard — Beta V1.4 Theme 4."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from database import init_db
from tests.conftest import run_db_test
from wallboard.service import _epss_movers_from_brief

# _seed_wallboard_db below writes via raw aiosqlite with SQLite-dialect SQL
# (datetime('now', ...)) — genuinely SQLite-only, not a fixture-pattern gap.
# A portable rewrite is Post-B (Postgres-native db/ conversion) scope, not
# this CI-gate PR's. Skip explicitly rather than silently passing/failing.
_requires_sqlite = pytest.mark.skipif(
    os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="_seed_wallboard_db uses raw SQLite-dialect SQL — portable rewrite is Post-B scope",
)


def _patch_app_lifecycle(monkeypatch) -> None:
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)


def _use_sqlite_backend(monkeypatch, db_path: Path) -> None:
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    from settings import settings as _settings
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    sqlite_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setattr("db.config.resolve_database_url", lambda: sqlite_url)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection._pool", None)


def _disable_rate_limit(monkeypatch) -> None:
    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.wallboard_bucket._buckets.pop("testclient", None)


async def _seed_wallboard_db(db_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

    db = await aiosqlite.connect(db_path)
    try:
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, cvss_score,
                published, modified, affected_products, summary, has_poc
            ) VALUES (
                'CVE-2024-9001', 'Log4j RCE on stack', 'CRITICAL', 1, 0.88, 9.8,
                datetime('now', '-3 days'), datetime('now', '-2 hours'),
                '["apache:log4j"]', 'Critical Log4j flaw', 1
            )
            """
        )
        await db.execute(
            """
            INSERT INTO cves (
                cve_id, description, severity, is_kev, epss_score, cvss_score,
                published, modified, affected_products, summary
            ) VALUES (
                'CVE-2024-9002', 'Other vendor issue', 'HIGH', 0, 0.42, 8.1,
                datetime('now', '-1 day'), datetime('now', '-6 hours'),
                '["vendor:product"]', 'High severity issue'
            )
            """
        )
        await db.execute(
            """
            INSERT INTO kev_deadlines (
                cve_id, product, short_description, required_action, due_date, date_added
            ) VALUES (
                'CVE-2024-9001', 'Log4j', 'RCE', 'Patch',
                date('now', '+10 days'), ?
            )
            """,
            (recent,),
        )
        await db.execute(
            """
            INSERT INTO cve_technique_map (cve_id, technique_id)
            VALUES ('CVE-2024-9001', 'T1190')
            """
        )
        await db.execute(
            """
            INSERT INTO mitre_techniques (technique_id, name, tactic, url)
            VALUES ('T1190', 'Exploit Public-Facing Application', 'Initial Access', '')
            """
        )
        await db.commit()
    finally:
        await db.close()


@pytest.fixture
def wallboard_client(tmp_path, monkeypatch):
    db_path = tmp_path / "wallboard.db"
    _use_sqlite_backend(monkeypatch, db_path)
    monkeypatch.setenv("BRIEFR_STACK_TERMS", "log4j")
    monkeypatch.setenv("WALLBOARD_TOKEN", "")

    _patch_app_lifecycle(monkeypatch)
    _disable_rate_limit(monkeypatch)

    run_db_test(init_db())
    run_db_test(_seed_wallboard_db(db_path))

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@_requires_sqlite
def test_wallboard_returns_v2_payload(wallboard_client):
    resp = wallboard_client.get("/api/wallboard")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "meta",
        "kev_on_stack",
        "kev_due_soon",
        "changes_24h",
        "top_risk",
        "ingest_health",
        "ingest_strip",
        "coverage_gaps",
        "epss_movers",
        "campaigns",
        "source_health",
        "headlines",
    ):
        assert key in body
    assert body["kev_on_stack"]["count"] == 1
    assert body["kev_on_stack"]["stack_configured"] is True
    assert body["top_risk"]["items"]
    assert body["ingest_health"]["status"] == "ok"
    assert "gap_count" in body["coverage_gaps"]
    assert "status" in body["ingest_strip"]


def test_wallboard_token_required_when_set(tmp_path, monkeypatch):
    db_path = tmp_path / "wallboard-auth.db"
    _use_sqlite_backend(monkeypatch, db_path)
    monkeypatch.setenv("WALLBOARD_TOKEN", "kiosk-secret-token")

    _patch_app_lifecycle(monkeypatch)
    _disable_rate_limit(monkeypatch)

    from settings import settings as _settings
    monkeypatch.setattr(_settings, "wallboard_token", "kiosk-secret-token")
    monkeypatch.setattr(_settings, "auth_cookie_secure", False)

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        denied = client.get("/api/wallboard")
        assert denied.status_code == 401

        ok_header = client.get(
            "/api/wallboard",
            headers={"X-BRIEFR-Wallboard-Token": "kiosk-secret-token"},
        )
        assert ok_header.status_code == 200

        # Sprint A7: query-string tokens leak into access logs — header only.
        denied_query = client.get("/api/wallboard?token=kiosk-secret-token")
        assert denied_query.status_code == 401

        session_resp = client.post(
            "/api/wallboard/session",
            json={"token": "kiosk-secret-token"},
        )
        assert session_resp.status_code == 200
        cookie_ok = client.get("/api/wallboard")
        assert cookie_ok.status_code == 200


def test_wallboard_rate_limited(tmp_path, monkeypatch):
    db_path = tmp_path / "wallboard-rl.db"
    _use_sqlite_backend(monkeypatch, db_path)

    _patch_app_lifecycle(monkeypatch)

    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", True)
    monkeypatch.setattr(_settings, "rate_limit_wallboard_per_minute", 2)
    _rl.wallboard_bucket.rate_per_minute = 2
    _rl.wallboard_bucket.capacity = 2.0
    _rl.wallboard_bucket.refill_per_second = 2 / 60.0
    _rl.wallboard_bucket._buckets.clear()

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/wallboard").status_code == 200
        assert client.get("/api/wallboard").status_code == 200
        blocked = client.get("/api/wallboard")
        assert blocked.status_code == 429
        assert blocked.headers.get("Retry-After")

    _rl.wallboard_bucket._buckets.clear()


@_requires_sqlite
def test_wallboard_response_has_no_admin_keys(wallboard_client):
    body = wallboard_client.get("/api/wallboard").json()
    dumped = str(body).lower()
    for forbidden in ("admin_api_key", "backup_age", "webhook_url", "api_key"):
        assert forbidden not in dumped


def test_epss_movers_from_brief_uses_positive_deltas():
    brief = {
        "sections": {
            "epss_movers": {
                "count": 1,
                "items": [{
                    "cve_id": "CVE-2024-1",
                    "epss_new": 0.42,
                    "epss_old": 0.12,
                    "epss_delta": 0.3,
                    "summary": "Example mover",
                }],
            },
        },
    }
    tile = _epss_movers_from_brief(brief)
    assert tile["count"] == 1
    assert tile["items"][0]["cve_id"] == "CVE-2024-1"
    assert tile["items"][0]["epss_delta"] == 0.3
    assert tile["items"][0]["epss_score"] == 0.42


def test_epss_movers_from_brief_empty_section():
    tile = _epss_movers_from_brief({"sections": {"epss_movers": {"count": 0, "items": []}}})
    assert tile["count"] == 0
    assert tile["items"] == []
