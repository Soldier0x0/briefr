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


def test_overflow_notes_before_footer():
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
    footer_idx = text.index("BRIEFR — generated")
    overflow_idx = text.index("more in BRIEFR")
    assert overflow_idx < footer_idx
    assert text[overflow_idx:footer_idx].strip().endswith("more in BRIEFR.")


def test_kev_date_added_uses_calendar_dates(db_env):
    from reports.daily_brief import collect_daily_brief

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            for cve_id, date_added in (
                ("CVE-2026-1111", "2026-08-25"),
                ("CVE-2026-2222", "2026-08-26"),
                ("CVE-2026-3333", "2026-08-27"),
            ):
                await db.execute(
                    """
                    INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                      severity, cvss_score, epss_score, is_kev, published)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cve_id,
                        "demo",
                        "",
                        "",
                        "CRITICAL",
                        0,
                        0,
                        1,
                        f"{date_added} 00:00:00",
                    ),
                )
                await db.execute(
                    """
                    INSERT INTO kev_deadlines (cve_id, product, short_description, date_added)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cve_id, "demo", f"kev {cve_id}", date_added),
                )
            await db.commit()
            brief = await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
            return brief
        finally:
            await db.close()

    brief = run_db_test(_seed())
    kev_ids = {row["cve_id"] for row in brief.kev}
    assert brief.counts["kev_new"] == 2
    assert kev_ids == {"CVE-2026-1111", "CVE-2026-2222"}


def test_stack_matches_admin_cpe_not_description(db_env):
    from auth.repo import create_user
    from preferences.repo import upsert_user_stack
    from reports.daily_brief import collect_daily_brief

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            user = await create_user(db, "ops", "correct-horse-battery", role="admin")
            await upsert_user_stack(db, user["id"], "nginx")
            for cve_id, affected, published, kev_date in (
                (
                    "CVE-2026-STACK1",
                    '["f5:nginx"]',
                    "2026-08-26 10:00:00",
                    None,
                ),
                (
                    "CVE-2026-STACK2",
                    '["apache:httpd"]',
                    "2026-08-26 11:00:00",
                    None,
                ),
                (
                    "CVE-2026-STACK3",
                    '["f5:nginx"]',
                    "2026-08-20 00:00:00",
                    "2026-08-26",
                ),
            ):
                await db.execute(
                    """
                    INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                      severity, cvss_score, epss_score, is_kev, published)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cve_id,
                        "nginx reverse proxy RCE" if "STACK1" in cve_id else "other",
                        affected,
                        "",
                        "CRITICAL",
                        0,
                        0,
                        1 if kev_date else 0,
                        published,
                    ),
                )
                if kev_date:
                    await db.execute(
                        """
                        INSERT INTO kev_deadlines (cve_id, product, short_description, date_added)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cve_id, "nginx", "kev on stack", kev_date),
                    )
            await db.commit()
            return await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    stack_ids = {row["cve_id"] for row in brief.stack}
    assert brief.counts["critical_high_new"] == 2
    assert brief.counts["kev_new"] == 1
    assert brief.counts["stack_matches"] == 2
    assert stack_ids == {"CVE-2026-STACK1", "CVE-2026-STACK3"}
    assert "CVE-2026-STACK2" not in stack_ids


def test_llm_lede_rejects_unknown_cve(db_env, monkeypatch):
    from reports.daily_brief import DailyBrief, apply_headline, COUNT_KEYS

    counts = {k: 0 for k in COUNT_KEYS}
    counts["kev_new"] = 1
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="a",
        window_end_local="b",
        generated_local="c",
        headline="",
        lede_source="template",
        counts=counts,
        kev=[{"cve_id": "CVE-2026-1111", "reason": "added to KEV", "severity": "HIGH"}],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
    )

    class Fake:
        content = "Also see CVE-1999-0001 which is critical."
        provider = "groq"
        model = "x"

    async def _fake(*args, **kwargs):
        return Fake()

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _fake)
    monkeypatch.setattr("reports.daily_brief.any_llm_provider_configured", lambda: True)

    async def _go():
        return await apply_headline(brief, llm_enabled=True)

    out = run_db_test(_go())
    assert "CVE-1999-0001" not in out.headline
    assert out.lede_source == "template"


def test_llm_disabled_never_calls(monkeypatch):
    called = {"n": 0}

    async def _fake(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not call")

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _fake)
    from reports.daily_brief import DailyBrief, apply_headline, template_headline, COUNT_KEYS

    zeros = {k: 0 for k in COUNT_KEYS}
    brief = DailyBrief(
        slot="standup",
        tz_name="UTC",
        window_start_local="a",
        window_end_local="b",
        generated_local="c",
        headline="",
        lede_source="template",
        counts=zeros,
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
    )

    async def _go():
        return await apply_headline(brief, llm_enabled=False)

    out = run_db_test(_go())
    assert called["n"] == 0
    assert out.headline == template_headline(brief)
