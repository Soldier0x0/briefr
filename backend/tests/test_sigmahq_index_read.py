"""Detect read path prefers SigmaHQ local index (U3)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection import rule_sources
from detection.sigmahq_index import SOURCE, apply_rules_from_dir
from tests.conftest import run_db_test

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "sigmahq_mini"

pytestmark_pg = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_find_sigma_rules_uses_index_without_github(monkeypatch):
    called = {"n": 0}

    async def fail_if_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("GitHub must not be called when index is populated")

    monkeypatch.setattr(rule_sources, "resilient_get", fail_if_called)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_matter")

    async def run():
        from database import get_db

        db = await get_db()
        await db.execute("DELETE FROM detection_rules WHERE source = $1", (SOURCE,))
        await db.commit()
        stats = await apply_rules_from_dir(
            db, FIXTURE_ROOT, commit_sha="readpathtest001readpathtest001readpa"
        )
        assert stats.seen == 3

        rules = await rule_sources.find_sigma_rules(
            db, "CVE-2021-44228", ["T1190"], github_token="ghp_x"
        )
        assert len(rules) == 1
        assert rules[0]["match_basis"] == "cve_exact"
        assert rules[0]["license"] == "DRL-1.1"
        assert "SigmaHQ" in rules[0]["attribution"]
        assert "jndi:" in rules[0]["content"]
        assert called["n"] == 0

        # Index populated but no CVE link → empty, still no GitHub
        empty = await rule_sources.find_sigma_rules(
            db, "CVE-2099-99999", ["T1190"], github_token="ghp_x"
        )
        assert empty == []
        assert called["n"] == 0

    run_db_test(run())


def test_allow_github_fallback_false_skips_network(monkeypatch, tmp_path):
    import database as db_module
    from database import get_db, init_db
    from tests.conftest import run_db_test

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "sigma_fb.db"))
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "sigma_fb.db"))
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    called = {"n": 0}

    async def fail_if_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("must not network")

    monkeypatch.setattr(rule_sources, "resilient_get", fail_if_called)

    async def run():
        await init_db()
        db = await get_db()
        try:
            rules = await rule_sources.find_sigma_rules(
                db,
                "CVE-2024-1234",
                ["T1190"],
                allow_github_fallback=False,
            )
            assert rules == []
            assert called["n"] == 0
        finally:
            await db.close()

    run_db_test(run())
