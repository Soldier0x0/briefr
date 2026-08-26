"""Daily brief collector + format grammar."""

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from database import get_db, init_db
from tests.conftest import run_db_test

pytestmark = pytest.mark.no_auth


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "daily_brief.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)
    run_db_test(init_db())
    return db_path


def test_quiet_window_format(db_env):
    from reports.daily_brief import collect_daily_brief, format_daily_brief_text, template_headline

    end = datetime(2026, 8, 26, 1, 30, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _go():
        db = await get_db()
        try:
            brief = await collect_daily_brief(
                db,
                slot="standup",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            brief = replace(brief, headline=template_headline(brief), lede_source="template")
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_go())
    assert brief.counts["kev_new"] == 0
    assert "Quiet window." in text
    assert "// COUNTS" in text
    assert "KEV new: 0" in text
    assert "slot=standup" in text
    assert "lede=template" in text


def test_kev_in_window_listed(db_env):
    from reports.daily_brief import collect_daily_brief, format_daily_brief_text

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                  severity, cvss_score, epss_score, is_kev, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "CVE-2026-1111",
                    "demo",
                    "",
                    "",
                    "CRITICAL",
                    0,
                    0,
                    1,
                    "2026-08-26 00:00:00",
                ),
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (cve_id, product, short_description, date_added)
                VALUES (?, ?, ?, ?)
                """,
                ("CVE-2026-1111", "demo", "demo kev", "2026-08-26"),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_seed())
    assert brief.counts["kev_new"] == 1
    assert "CVE-2026-1111" in text
    assert "// KEV" in text


def test_overflow_drops_ops_before_kev():
    from reports.daily_brief import DailyBrief, format_daily_brief_text

    items = [f"CVE-2026-{i:04d}" for i in range(40)]
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="Busy.",
        lede_source="template",
        counts={
            "kev_new": 40,
            "stack_matches": 0,
            "watchlist": 0,
            "ioc_hits": 0,
            "critical_high_new": 0,
            "ops_issues": 20,
        },
        kev=[{"cve_id": c, "reason": "added to KEV", "severity": "HIGH"} for c in items],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[{"id": f"job-{i}", "reason": "boom " * 40} for i in range(20)],
    )
    text = format_daily_brief_text(brief, limit=500)
    assert len(text) <= 500
    assert "// COUNTS" in text
    assert "// OPS" not in text or "more in BRIEFR" in text
