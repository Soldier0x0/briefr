"""Q4 Tier A stack backfill."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from db.stack_backfill import estimate_eta, products_from_profile, stack_backfill_enabled


def test_estimate_eta_and_products():
    products = products_from_profile(
        {
            "operatingSystems": [{"product": "Ubuntu", "version": "22.04"}],
            "applications": [{"product": "nginx", "vendor": "nginx", "version": "1.18"}],
        },
        "openssl",
    )
    assert len(products) >= 3
    eta = estimate_eta(products)
    assert eta["eta_low_seconds"] <= eta["eta_high_seconds"]
    assert eta["nvd_calls_est"] >= 1


def test_agree_disabled_returns_403(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "bf.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("STACK_BACKFILL_ENABLED", "0")
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        res = client.post("/api/stack/backfill/agree")
        assert res.status_code == 403


def test_coverage_and_agree_flow(tmp_path, monkeypatch, auth_token):
    db_path = tmp_path / "bf2.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("STACK_BACKFILL_ENABLED", "1")
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setattr(_settings, "rate_limit_enabled", False)

    async def _fake_page(keyword, *, start_index=0, api_key=None, results_per_page=2000):
        return (
            [
                {
                    "cve_id": "CVE-2024-99999",
                    "description": f"{keyword} issue",
                    "cvss_score": 7.5,
                    "severity": "HIGH",
                    "published": "2024-01-01T00:00:00",
                    "modified": "2024-01-02T00:00:00",
                    "affected_products": [keyword],
                    "cpe_matches": [],
                    "cwe_ids": [],
                    "source_urls": [],
                    "is_kev": 0,
                    "epss_score": None,
                    "has_poc": 0,
                    "patch_available": 0,
                    "mitre_technique": None,
                    "summary": None,
                }
            ],
            1,
            None,
        )

    async def _empty_epss(ids):
        return {}

    async def _empty_kev():
        return []

    async def _kick_sync(run_id: int):
        from services.stack_backfill_worker import process_stack_backfill_run

        await process_stack_backfill_run(run_id)

    monkeypatch.setattr(
        "services.stack_backfill_worker.fetch_cves_keyword_page",
        _fake_page,
    )
    monkeypatch.setattr("services.stack_backfill_worker.fetch_epss_bulk", _empty_epss)
    monkeypatch.setattr("services.stack_backfill_worker.fetch_kev", _empty_kev)
    monkeypatch.setattr("routers.stack_catalog._kick_backfill", _kick_sync)
    monkeypatch.setattr("routers.stack_catalog.stack_backfill_enabled", lambda: True)
    monkeypatch.setattr("db.stack_backfill.stack_backfill_enabled", lambda: True)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set("briefr_at", auth_token())
        # Unique term so seeded/shared DBs cannot inflate hit counts.
        put = client.put(
            "/api/me/stack",
            json={"stack_terms": "zzq4uniqueproduct999"},
        )
        assert put.status_code == 200
        assert put.json().get("stack_terms") == "zzq4uniqueproduct999"
        cov = client.get("/api/stack/coverage")
        assert cov.status_code == 200
        body = cov.json()
        assert body["enabled"] is True, body
        assert body["shallow_count"] >= 1, body
        assert body["needs_backfill"] is True, body
        agree = client.post("/api/stack/backfill/agree")
        assert agree.status_code == 200
        run_id = agree.json()["run_id"]
        status = client.get(f"/api/stack/backfill/{run_id}")
        assert status.status_code == 200
        assert status.json()["run"]["status"] == "completed"
        assert status.json()["run"]["cves_upserted"] >= 1


def test_stack_backfill_flag_default_off(monkeypatch):
    monkeypatch.delenv("STACK_BACKFILL_ENABLED", raising=False)
    assert stack_backfill_enabled() is False
