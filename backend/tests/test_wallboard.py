"""Tests for GET /api/wallboard — Beta V1.4 Theme 4."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db
import pytest
from fastapi.testclient import TestClient

from database import init_db
from tests.conftest import run_db_test
from wallboard.service import _epss_movers_from_brief


def _patch_app_lifecycle(monkeypatch) -> None:
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)


def _use_sqlite_backend(monkeypatch, db_path: Path) -> None:
    """SQLite removed — isolation is session Postgres + TRUNCATE."""
    del monkeypatch, db_path


def _disable_rate_limit(monkeypatch) -> None:
    import rate_limit as _rl
    from settings import settings as _settings

    monkeypatch.setattr(_settings, "rate_limit_enabled", False)
    _rl.wallboard_bucket._buckets.pop("testclient", None)


def _open_or_static_wallboard_gate(
    monkeypatch, *, token: str = ""
) -> dict[str, str]:
    """Turn off auto-token seeding so tests control the kiosk gate.

    Default auto-token True seeds a rotated secret on lifespan, which 401s
    unauthenticated GET /api/wallboard (Postgres CI: test_wallboard_rate_limited).
    """
    from settings import settings as _settings
    from wallboard.token_store import _invalidate_caches

    monkeypatch.setattr(_settings, "wallboard_auto_token", False)
    monkeypatch.setattr(_settings, "wallboard_token", token)
    monkeypatch.setenv("WALLBOARD_TOKEN", token)
    _invalidate_caches()
    if token:
        return {"X-BRIEFR-Wallboard-Token": token}
    return {}


async def _seed_wallboard_db(db_path: Path) -> None:
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

    db = await get_db()
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
    _open_or_static_wallboard_gate(monkeypatch)

    _patch_app_lifecycle(monkeypatch)
    _disable_rate_limit(monkeypatch)

    run_db_test(init_db())
    run_db_test(_seed_wallboard_db(db_path))

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


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
    top = body["top_risk"]["items"][0]
    assert "threat_score" in top
    assert "op_band" in top
    assert top["risk_score"] == top["threat_score"]
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
    # Monkeypatch bucket fields so get_bucket_stats / later tests see defaults restored
    monkeypatch.setattr(_rl.wallboard_bucket, "rate_per_minute", 2)
    monkeypatch.setattr(_rl.wallboard_bucket, "capacity", 2.0)
    monkeypatch.setattr(_rl.wallboard_bucket, "refill_per_second", 2 / 60.0)
    _rl.wallboard_bucket._buckets.clear()
    headers = _open_or_static_wallboard_gate(monkeypatch, token="kiosk-rl-token")

    from main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/wallboard", headers=headers).status_code == 200
        assert client.get("/api/wallboard", headers=headers).status_code == 200
        blocked = client.get("/api/wallboard", headers=headers)
        assert blocked.status_code == 429
        assert blocked.headers.get("Retry-After")

    _rl.wallboard_bucket._buckets.clear()


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


def test_top_risk_rank_prefers_op_then_threat_over_legacy_blend():
    """W2: CISA KEV (P1) ranks above VulnCheck-high legacy v1.1b total (P2)."""
    from datetime import date, timedelta

    from scoring.environment import classify_environment
    from scoring.priority import derive_operational_priority, operational_priority_sort_key
    from scoring.risk import calculate_risk_score
    from scoring.threat import calculate_threat_score
    from wallboard.service import score_cve_for_top_risk

    kev_date = (date.today() - timedelta(days=3)).isoformat()
    cisa = {
        "cve_id": "CVE-2024-CISA",
        "is_kev": True,
        "kev_date_added": kev_date,
        "epss_score": 0.01,
        "cvss_score": 5.0,
        "severity": "MEDIUM",
        "summary": "CISA KEV low additive",
        "has_poc": False,
        "public_exploits": [],
    }
    vulncheck = {
        "cve_id": "CVE-2024-VCHECK",
        "is_kev": False,
        "is_vulncheck_exploited": True,
        "epss_score": 0.9,
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "summary": "VulnCheck high legacy blend",
        "has_poc": True,
        "public_exploits": [{"type": "poc"}],
    }

    legacy_order = sorted(
        [cisa, vulncheck],
        key=lambda c: calculate_risk_score(c, momentum_score=0.0).get("total") or 0,
        reverse=True,
    )
    assert legacy_order[0]["cve_id"] == "CVE-2024-VCHECK"

    scored = [
        score_cve_for_top_risk(cisa, momentum_score=0.0),
        score_cve_for_top_risk(vulncheck, momentum_score=0.0),
    ]
    scored = [s for s in scored if s]
    scored.sort(key=lambda item: item["_sort_key"])
    assert scored[0]["cve_id"] == "CVE-2024-CISA"
    assert scored[0]["op_band"] == "P1"
    assert scored[0]["threat_score"] >= 80
    assert scored[1]["cve_id"] == "CVE-2024-VCHECK"
    assert scored[1]["op_band"] == "P2"
    # Backward-compat field mirrors Threat, not legacy blend
    assert scored[0]["risk_score"] == scored[0]["threat_score"]

    # Sanity: OP/Threat path matches ADR helpers
    t = calculate_threat_score(cisa, momentum_score=0.0)
    env = classify_environment(cisa, None)
    op = derive_operational_priority(t["band"], env["tier"])
    assert scored[0]["_sort_key"] == operational_priority_sort_key(
        op["band"], t["score"], env["tier"], cisa["cve_id"]
    )
