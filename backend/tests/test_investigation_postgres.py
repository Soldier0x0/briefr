"""Postgres-gated INVESTIGATE route smoke (real DATABASE_URL, no SQLite monkeypatch)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test, seed_pytest_auth_user_if_missing

from correlation.campaigns import build_campaigns_from_pulses
from database import init_db, replace_otx_cve_pulses, replace_otx_pulse_iocs
import database
from main import app


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not PostgreSQL",
)
def test_investigate_cve_relationships_on_postgres(monkeypatch):
    async def _noop_async() -> None:
        return None

    monkeypatch.setattr("main.start_scheduler", lambda: None)
    monkeypatch.setattr("main.stop_scheduler", lambda: None)
    monkeypatch.setattr("main.maybe_run_on_startup", _noop_async)

    cve_id = "CVE-2024-99101"

    async def seed():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published, is_kev, has_poc, epss_score)
                VALUES (?, 'postgres investigate', '2024-06-01', 0, 0, 0.5)
                ON CONFLICT (cve_id) DO NOTHING
                """,
                (cve_id,),
            )
            pulses = [
                {
                    "pulse_id": "pulse-investigate-pg",
                    "pulse_name": "PG pulse",
                    "author": "analyst",
                    "created_date": "2024-01-10",
                    "adversary": "",
                    "malware_families": [],
                    "tags": [],
                    "targeted_countries": [],
                    "ioc_count": 1,
                }
            ]
            await replace_otx_cve_pulses(db, cve_id, pulses)
            await replace_otx_pulse_iocs(
                db,
                "pulse-investigate-pg",
                [{"ioc_type": "domain", "ioc_value": "evil.pg.example", "description": ""}],
            )
            await build_campaigns_from_pulses(db)
            await db.commit()
        finally:
            await db.close()

    seed_pytest_auth_user_if_missing()

    # Seed inside an active TestClient lifespan so run_db_test restores the
    # pool bound to the client's event loop (see test_db_explorer._seed_cve).
    with TestClient(app) as client:
        run_db_test(seed())

        resolve = client.get("/api/investigations/resolve", params={"q": cve_id})
        assert resolve.status_code == 200, resolve.text

        relationships = client.get(
            f"/api/investigations/entities/cve/{cve_id}/relationships"
        )
        assert relationships.status_code == 200, relationships.text
        body = relationships.json()
        assert body["root"]["node_id"] == f"cve:{cve_id}"
