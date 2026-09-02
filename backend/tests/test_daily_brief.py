"""Daily brief collector + format grammar."""

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from database import get_db, get_sync_state_value, init_db, set_sync_state_value
from reports.daily_brief import (
    COUNT_KEYS,
    DailyBrief,
    _window_for_slot,
    apply_headline,
    brief_to_payload,
    collect_daily_brief,
    format_daily_brief_text,
    run_daily_brief_slot,
    template_headline,
)
from reports.market_clusters import cluster_published
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
    assert "At a glance" in text
    assert "New on CISA KEV: 0" in text
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
    assert "CISA KEV" in text


def test_notification_sections_collect_on_sqlite(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-operator", "hash", "admin", 1),
            )
            rows = (
                (
                    1,
                    "analyst",
                    "watchlist",
                    "high",
                    "CVE-2026-1111 — EPSS jump",
                    "EPSS crossed the watch threshold",
                    "cve",
                    "CVE-2026-1111",
                    "watch:CVE-2026-1111:epss",
                    "2026-08-26 10:00:00",
                ),
                (
                    1,
                    "analyst",
                    "ioc_watchlist",
                    "high",
                    "IOC watchlist hit (threatfox)",
                    "IOC watchlist hit (THREATFOX): DOMAIN evil.example",
                    "ioc",
                    "evil.example",
                    "ioc:1:evil.example:threatfox",
                    "2026-08-26 10:01:00",
                ),
                (
                    1,
                    "operator",
                    "job_error",
                    "critical",
                    "Job failed: nvd_incremental_sync",
                    "TimeoutError",
                    "job",
                    "nvd_incremental_sync",
                    "job:nvd_incremental_sync:timeout",
                    "2026-08-26 10:02:00",
                ),
            )
            await db.executemany(
                """
                INSERT INTO user_notifications (
                    user_id, scope, category, severity, title, body,
                    entity_type, entity_id, dedupe_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                list(rows),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_seed())
    assert brief.counts["watchlist"] == 1
    assert brief.counts["ioc_hits"] == 1
    assert brief.counts["ops_issues"] == 1
    assert "Pinned CVEs" in text
    assert "IOC watch" in text
    assert "Instance problems" in text
    assert "• CVE-2026-1111 — EPSS jump" in text
    assert "• CVE-2026-1111 — CVE-2026-1111" not in text
    assert "• DOMAIN evil.example — THREATFOX" in text
    assert "Scheduler job failed: NVD Incremental Sync" in text


async def _insert_job_error_rows(db, *, job_id: str, count: int, created_at: str):
    rows = []
    for i in range(count):
        rows.append(
            (
                1,
                "operator",
                "job_error",
                "critical",
                f"Job failed: {job_id}",
                f"KEV request failed {i}",
                "job",
                job_id,
                f"job:{job_id}:fail-{i}",
                created_at,
            )
        )
    await db.executemany(
        """
        INSERT INTO user_notifications (
            user_id, scope, category, severity, title, body,
            entity_type, entity_id, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def test_ops_omits_resolved_job_errors_from_created_at_window(db_env):
    import json

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-operator", "hash", "admin", 1),
            )
            await _insert_job_error_rows(
                db,
                job_id="kev_metadata_sync",
                count=3,
                created_at="2026-08-26 10:02:00",
            )
            await set_sync_state_value(
                db,
                "scheduler.last_run.kev_metadata_sync",
                json.dumps(
                    [
                        {
                            "had_error": False,
                            "error_message": "",
                            "started_at": "2026-08-26T17:00:00+00:00",
                        }
                    ]
                ),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_seed())
    assert brief.counts["ops_issues"] == 0
    assert brief.ops == []
    assert "Scheduler job failed: KEV Metadata Sync" not in text


def test_ops_dedupes_current_job_failure_to_one_line(db_env):
    import json

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-operator", "hash", "admin", 1),
            )
            await _insert_job_error_rows(
                db,
                job_id="kev_metadata_sync",
                count=3,
                created_at="2026-08-26 10:02:00",
            )
            await set_sync_state_value(
                db,
                "scheduler.last_run.kev_metadata_sync",
                json.dumps(
                    [
                        {
                            "had_error": True,
                            "error_message": "KEV request failed",
                            "started_at": "2026-08-26T17:00:00+00:00",
                        }
                    ]
                ),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_seed())
    assert brief.counts["ops_issues"] == 1
    assert [row["id"] for row in brief.ops] == ["kev_metadata_sync"]
    assert text.count("Scheduler job failed: KEV Metadata Sync") == 1


def test_ops_keeps_last_run_failure_after_job_error_dismissed(db_env):
    import json

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-operator", "hash", "admin", 1),
            )
            await db.execute(
                """
                INSERT INTO user_notifications (
                    user_id, scope, category, severity, title, body,
                    entity_type, entity_id, dedupe_key, created_at, dismissed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "operator",
                    "job_error",
                    "critical",
                    "Job failed: kev_metadata_sync",
                    "old timeout",
                    "job",
                    "kev_metadata_sync",
                    "job:kev_metadata_sync:old",
                    "2026-08-26 10:02:00",
                    "2026-08-26 11:00:00",
                ),
            )
            await set_sync_state_value(
                db,
                "scheduler.last_run.kev_metadata_sync",
                json.dumps(
                    [
                        {
                            "had_error": True,
                            "error_message": "still failing",
                            "started_at": "2026-08-26T17:00:00+00:00",
                        }
                    ]
                ),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            return brief
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.counts["ops_issues"] == 1
    assert brief.ops[0]["id"] == "kev_metadata_sync"
    assert "still failing" in brief.ops[0]["reason"]


def test_job_error_dsn_is_redacted_from_formatted_text(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)
    error = (
        "ConnectionError: could not connect to "
        "postgresql://briefr:hunter2@127.0.0.1:5432/briefr"
    )

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-operator", "hash", "admin", 1),
            )
            await db.execute(
                """
                INSERT INTO user_notifications (
                    user_id, scope, category, severity, title, body,
                    entity_type, entity_id, dedupe_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "operator",
                    "job_error",
                    "critical",
                    "Job failed: nvd_incremental_sync",
                    error,
                    "job",
                    "nvd_incremental_sync",
                    "job:nvd_incremental_sync:dsn",
                    "2026-08-26 10:02:00",
                ),
            )
            await db.commit()
            brief = await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            return format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    text = run_db_test(_seed())
    assert "Scheduler job failed: NVD Incremental Sync" in text
    assert "hunter2" not in text
    assert "postgresql://" not in text


def test_notification_fanout_counts_one_event_per_dedupe_key(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            users = [
                (user_id, f"daily-brief-user-{user_id}", "hash", "analyst", 1)
                for user_id in range(1, 4)
            ]
            await db.executemany(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                users,
            )
            notifications = [
                (
                    user_id,
                    "analyst",
                    "watchlist",
                    "high",
                    "CVE-2026-1111 — EPSS jump",
                    "EPSS crossed the watch threshold",
                    "cve",
                    "CVE-2026-1111",
                    "watch:CVE-2026-1111:epss",
                    "2026-08-26 10:00:00",
                )
                for user_id in range(1, 4)
            ]
            await db.executemany(
                """
                INSERT INTO user_notifications (
                    user_id, scope, category, severity, title, body,
                    entity_type, entity_id, dedupe_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                notifications,
            )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.counts["watchlist"] == 1
    assert len(brief.watchlist) == 1
    assert brief.watchlist[0]["cve_id"] == "CVE-2026-1111"


def test_collector_uses_utc_bounds_with_non_utc_display(db_env):
    end = datetime(2026, 8, 26, 12, 30, tzinfo=timezone.utc)
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
                    "CVE-2026-UTCBOUND",
                    "inside the UTC window",
                    "",
                    "",
                    "CRITICAL",
                    0,
                    0,
                    0,
                    "2026-08-25 14:00:00",
                ),
            )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="Asia/Kolkata",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.window_start_local == "2026-08-25 18:00"
    assert brief.window_end_local == "2026-08-26 18:00"
    assert brief.counts["critical_high_new"] == 1


def test_collector_accepts_nvd_published_timestamp(db_env):
    end = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
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
                    "CVE-2026-NVDFMT",
                    "NVD timestamp format",
                    "",
                    "",
                    "HIGH",
                    0,
                    0,
                    0,
                    "2026-08-26T10:00:00.000",
                ),
            )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.counts["critical_high_new"] == 1
    assert [row["cve_id"] for row in brief.stack] == []


def test_market_clusters_all_published_not_just_critical(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            for cve_id, sev, cpe, pub in (
                (
                    "CVE-2026-M1",
                    "MEDIUM",
                    '[{"product":"nginx"}]',
                    "2026-08-26T10:00:00.000",
                ),
                (
                    "CVE-2026-M2",
                    "CRITICAL",
                    '[{"product":"openssl"}]',
                    "2026-08-26T11:00:00.000",
                ),
                ("CVE-2026-M3", "LOW", "", "2026-08-26T12:00:00.000"),
                (
                    "CVE-2026-OLD",
                    "HIGH",
                    '[{"product":"nginx"}]',
                    "2026-08-20T10:00:00.000",
                ),
            ):
                await db.execute(
                    """
                    INSERT INTO cves (cve_id, description, affected_products, mitre_technique,
                                      severity, cvss_score, epss_score, is_kev, published, cpe_matches)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cve_id, "demo", "[]", "", sev, 0, 0, 0, pub, cpe),
                )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.market["published"] == 3
    labels = [product["label"] for product in brief.market["products"]]
    assert "openssl" in labels
    assert "nginx" in labels
    assert "Unmapped" in labels
    assert "Quiet window." not in template_headline(brief)
    text = format_daily_brief_text(brief, limit=2000)
    assert "Products" in text
    assert text.index("Products") > text.index("At a glance")
    assert "Published: 3" in text
    assert "CVE-2026-OLD" not in text
    assert brief_to_payload(brief)["market"]["published"] == 3


def test_headline_skips_unanalyzed_market_leader():
    rows = [
        {"severity": "MEDIUM", "cpe_matches": "", "affected_products": ""}
        for _ in range(200)
    ]
    rows.append(
        {
            "severity": "CRITICAL",
            "cpe_matches": '[{"product":"nginx"}]',
            "affected_products": "",
        }
    )
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        market=cluster_published(rows),
    )

    headline = template_headline(brief)

    assert "nginx led volume." in headline
    assert "unanalyzed led volume." not in headline
    assert "Unmapped" in format_daily_brief_text(brief, limit=2000)

    unanalyzed_only = replace(brief, market=cluster_published(rows[:-1]))
    unanalyzed_headline = template_headline(unanalyzed_only)
    assert "200 published." in unanalyzed_headline
    assert "led volume." not in unanalyzed_headline


def test_headline_with_only_medium_published_cves_is_not_quiet():
    market = cluster_published(
        [
            {
                "severity": "MEDIUM",
                "cpe_matches": '[{"product":"nginx"}]',
                "affected_products": "",
            }
        ]
    )
    brief = DailyBrief(
        slot="standup",
        tz_name="UTC",
        window_start_local="2026-08-26 06:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        market=market,
    )

    headline = template_headline(brief)

    assert headline != "Quiet window."
    assert "published" in headline


def test_template_headline_uses_singular_stack_match():
    counts = {key: 0 for key in COUNT_KEYS}
    counts["kev_new"] = 2
    counts["stack_matches"] = 1
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="",
        lede_source="template",
        counts=counts,
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
    )

    headline = template_headline(brief)

    assert "1 stack match." in headline
    assert "1 stack matches." not in headline
    assert "1 matches My Stack" not in headline


def test_market_cluster_fetch_prefers_newest_when_capped(db_env, monkeypatch):
    monkeypatch.setattr("reports.daily_brief._MARKET_QUERY_LIMIT", 2)
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            for cve_id, product, published in (
                ("CVE-2026-OLD1", "nginx", "2026-08-26T10:00:00.000"),
                ("CVE-2026-MID1", "openssl", "2026-08-26T11:00:00.000"),
                ("CVE-2026-NEW1", "python", "2026-08-26T12:00:00.000"),
            ):
                await db.execute(
                    """
                    INSERT INTO cves (
                        cve_id, description, affected_products, mitre_technique,
                        severity, cvss_score, epss_score, is_kev, published, cpe_matches
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cve_id,
                        "market order",
                        "[]",
                        "",
                        "MEDIUM",
                        0,
                        0,
                        0,
                        published,
                        f'[{{"product":"{product}"}}]',
                    ),
                )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    labels = [product["label"] for product in brief.market["products"]]
    assert brief.market["published"] == 3
    assert "python" in labels
    assert "openssl" in labels
    assert "nginx" not in labels


def test_market_header_totals_are_untruncated_when_clustering_is_capped(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            cves = []
            for index in range(5001):
                severity = "CRITICAL"
                if index == 4998:
                    severity = "HIGH"
                elif index == 4999:
                    severity = "LOW"
                elif index == 5000:
                    severity = "UNKNOWN"
                cves.append(
                    (
                        f"CVE-2026-MARKET{index:04d}",
                        "market cap",
                        '["f5:nginx"]',
                        "",
                        severity,
                        0,
                        0,
                        0,
                        "2026-08-26T10:00:00.000",
                    )
                )
            await db.executemany(
                """
                INSERT INTO cves (
                    cve_id, description, affected_products, mitre_technique,
                    severity, cvss_score, epss_score, is_kev, published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                cves,
            )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.market["published"] == 5001
    assert brief.market["critical"] == 4998
    assert brief.market["high"] == 1
    assert brief.market["medium"] == 1
    assert brief.market["low"] == 1
    assert sum(product["total"] for product in brief.market["products"]) == 5000


def test_overflow_never_drops_populated_market():
    items = [f"CVE-2026-{i:04d}" for i in range(40)]
    market = cluster_published(
        [
            {
                "severity": "HIGH",
                "cpe_matches": f'[{{"product":"product-{i}"}}]',
                "affected_products": "",
            }
            for i in range(6)
        ]
    )
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
            "critical_high_new": 6,
            "ops_issues": 20,
        },
        kev=[{"cve_id": c, "reason": "added to KEV", "severity": "HIGH"} for c in items],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[{"id": f"job-{i}", "reason": "boom " * 40} for i in range(20)],
        market=market,
    )

    text = format_daily_brief_text(brief, limit=700)

    assert len(text) <= 700
    assert "Products" in text
    assert "Published: 6" in text
    assert "job-0" not in text
    assert "CVE-2026-" not in text


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
    assert "At a glance" in text
    assert "Instance problems" not in text or "more in BRIEFR" in text


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
    assert brief.counts["kev_new"] == 1
    assert kev_ids == {"CVE-2026-2222"}


def test_same_day_window_includes_kev_added_that_date(db_env):
    from reports.daily_brief import collect_daily_brief

    start = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)

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
                    "CVE-2026-SAMEDAY",
                    "demo",
                    "",
                    "",
                    "HIGH",
                    0,
                    0,
                    1,
                    "2026-08-26 09:00:00",
                ),
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (cve_id, product, short_description, date_added)
                VALUES (?, ?, ?, ?)
                """,
                ("CVE-2026-SAMEDAY", "demo", "added today", "2026-08-26"),
            )
            await db.commit()
            return await collect_daily_brief(
                db, slot="standup", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.counts["kev_new"] == 1
    assert {row["cve_id"] for row in brief.kev} == {"CVE-2026-SAMEDAY"}


def test_collector_caps_lists_but_keeps_untruncated_counts(db_env):
    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "daily-brief-cap-operator", "hash", "admin", 1),
            )
            await db.execute(
                """
                INSERT INTO user_preferences (user_id, stack_terms, updated_at)
                VALUES (?, ?, ?)
                """,
                (1, "nginx", "2026-08-26 09:00:00"),
            )
            cves = [
                (
                    f"CVE-2026-CAP{i:03d}",
                    "count/list cap",
                    '["acme:nginx"]',
                    "",
                    "HIGH",
                    0,
                    0,
                    0,
                    f"2026-08-26T10:{i % 60:02d}:00.000",
                )
                for i in range(55)
            ]
            await db.executemany(
                """
                INSERT INTO cves (
                    cve_id, description, affected_products, mitre_technique,
                    severity, cvss_score, epss_score, is_kev, published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                cves,
            )
            notifications = [
                (
                    1,
                    "analyst",
                    "watchlist",
                    "high",
                    f"CVE-2026-CAP{i:03d} — EPSS jump",
                    "EPSS crossed the watch threshold",
                    "cve",
                    f"CVE-2026-CAP{i:03d}",
                    f"watch:CVE-2026-CAP{i:03d}:epss",
                    f"2026-08-26 11:{i % 60:02d}:00",
                )
                for i in range(55)
            ]
            await db.executemany(
                """
                INSERT INTO user_notifications (
                    user_id, scope, category, severity, title, body,
                    entity_type, entity_id, dedupe_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                notifications,
            )
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_seed())
    assert brief.counts["critical_high_new"] == 55
    assert brief.counts["stack_matches"] == 55
    assert brief.counts["watchlist"] == 55
    assert len(brief.stack) == 50
    assert len(brief.watchlist) == 50
    assert len(brief.kev) <= 50
    assert len(brief.ioc) <= 50
    assert len(brief.ops) <= 50


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
                (
                    "CVE-2026-STACK4",
                    '["apache:httpd"]',
                    "2026-08-26 12:00:00",
                    None,
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
                        (
                            "nginx reverse proxy RCE"
                            if cve_id in {"CVE-2026-STACK1", "CVE-2026-STACK4"}
                            else "other"
                        ),
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
    assert brief.counts["critical_high_new"] == 3
    assert brief.counts["kev_new"] == 1
    assert brief.counts["stack_matches"] == 2
    assert stack_ids == {"CVE-2026-STACK1", "CVE-2026-STACK3"}
    assert "CVE-2026-STACK2" not in stack_ids
    assert "CVE-2026-STACK4" not in stack_ids


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


def test_llm_fact_block_redacts_ops_error_strings(monkeypatch):
    counts = {key: 0 for key in COUNT_KEYS}
    counts["ops_issues"] = 1
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="",
        lede_source="template",
        counts=counts,
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[
            {
                "id": "nvd_incremental_sync",
                "reason": "ConnectionError at /srv/briefr/private/provider-token",
                "error_class": "job_error",
            }
        ],
    )
    captured = {"fact_block": ""}

    class Fake:
        content = "One ops issue needs attention."
        provider = "groq"
        model = "x"

    async def _fake(*args, **kwargs):
        captured["fact_block"] = kwargs["messages"][1]["content"]
        return Fake()

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _fake)
    monkeypatch.setattr("reports.daily_brief.any_llm_provider_configured", lambda: True)

    out = run_db_test(apply_headline(brief, llm_enabled=True))
    assert out.lede_source == "groq"
    assert "/srv/briefr/private/provider-token" not in captured["fact_block"]
    assert "ConnectionError" not in captured["fact_block"]
    assert "job_error" in captured["fact_block"]


def test_llm_exception_falls_back_to_template(monkeypatch):
    counts = {key: 0 for key in COUNT_KEYS}
    counts["ops_issues"] = 1
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="",
        lede_source="template",
        counts=counts,
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
    )

    async def _raise(*args, **kwargs):
        raise RuntimeError("metering unavailable")

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _raise)
    monkeypatch.setattr("reports.daily_brief.any_llm_provider_configured", lambda: True)

    out = run_db_test(apply_headline(brief, llm_enabled=True))
    assert out.lede_source == "template"
    assert out.headline == "1 instance problem."


def test_standup_without_watermark_uses_twelve_hours(db_env, monkeypatch):
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "1")
    end = datetime(2026, 8, 26, 7, 0, tzinfo=timezone.utc)

    async def _go():
        db = await get_db()
        try:
            return await _window_for_slot(db, "standup", window_end_utc=end)
        finally:
            await db.close()

    start, returned_end = run_db_test(_go())
    assert returned_end == end
    assert start == end - timedelta(hours=12)


def test_standup_ignores_watermark_when_eod_disabled(db_env, monkeypatch):
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "0")
    end = datetime(2026, 8, 26, 7, 0, tzinfo=timezone.utc)

    async def _go():
        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                "daily_brief:last_eod_end",
                "2026-08-25T18:00:00Z",
            )
            await db.commit()
            return await _window_for_slot(db, "standup", window_end_utc=end)
        finally:
            await db.close()

    start, returned_end = run_db_test(_go())
    assert returned_end == end
    assert start == end - timedelta(hours=12)


def test_standup_clamps_stale_watermark_to_twenty_four_hours(db_env, monkeypatch):
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "1")
    end = datetime(2026, 8, 26, 7, 0, tzinfo=timezone.utc)

    async def _go():
        db = await get_db()
        try:
            await set_sync_state_value(
                db,
                "daily_brief:last_eod_end",
                "2026-08-20T18:00:00Z",
            )
            await db.commit()
            return await _window_for_slot(db, "standup", window_end_utc=end)
        finally:
            await db.close()

    start, returned_end = run_db_test(_go())
    assert returned_end == end
    assert start == end - timedelta(hours=24)


def test_run_daily_brief_slot_disabled_skips(monkeypatch, db_env):
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "0")
    from reports.daily_brief import run_daily_brief_slot

    called = {"n": 0}

    async def fake_dispatch(*_a, **_k):
        called["n"] += 1
        return {"status": "ok", "sent": [], "errors": {}}

    monkeypatch.setattr("reports.daily_brief.dispatch_event", fake_dispatch)

    result = run_db_test(run_daily_brief_slot("eod"))
    assert result == {"status": "skipped", "reason": "disabled", "slot": "eod"}
    assert called["n"] == 0


def test_run_daily_brief_standup_skips_overlapping(monkeypatch, db_env):
    from database import set_sync_state_value
    from reports.daily_brief import run_daily_brief_slot

    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "1")
    monkeypatch.setenv("DAILY_BRIEF_STANDUP_ENABLED", "1")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "UTC")
    called = {"n": 0}

    async def fake_dispatch(*_a, **_k):
        called["n"] += 1
        return {"status": "ok", "sent": ["discord"], "errors": {}}

    monkeypatch.setattr("reports.daily_brief.dispatch_event", fake_dispatch)

    async def seed():
        db = await get_db()
        try:
            now = datetime.now(timezone.utc)
            await set_sync_state_value(
                db,
                "daily_brief:last_eod_end",
                (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            await db.commit()
        finally:
            await db.close()

    run_db_test(seed())

    result = run_db_test(run_daily_brief_slot("standup"))
    assert result["status"] == "skipped"
    assert result["reason"] == "overlapping"
    assert result["slot"] == "standup"
    assert called["n"] == 0


def test_run_daily_brief_eod_writes_watermark(monkeypatch, db_env):
    from database import get_sync_state_value
    from reports.daily_brief import run_daily_brief_slot

    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "1")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "UTC")
    monkeypatch.setenv("DAILY_BRIEF_LLM_ENABLED", "0")

    async def fake_dispatch(*_a, **_k):
        return {"status": "ok", "sent": ["discord"], "errors": {}, "event_type": "daily_brief"}

    monkeypatch.setattr("reports.daily_brief.dispatch_event", fake_dispatch)

    result = run_db_test(run_daily_brief_slot("eod"))
    assert result["status"] == "ok"
    assert result["slot"] == "eod"

    async def check():
        db = await get_db()
        try:
            return await get_sync_state_value(db, "daily_brief:last_eod_end")
        finally:
            await db.close()

    watermark = run_db_test(check())
    assert watermark is not None
    assert watermark.endswith("Z")


def test_run_daily_brief_failed_eod_does_not_write_watermark(monkeypatch, db_env):
    monkeypatch.setenv("DAILY_BRIEF_EOD_ENABLED", "1")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "UTC")
    monkeypatch.setenv("DAILY_BRIEF_LLM_ENABLED", "0")

    async def fake_dispatch(*_a, **_k):
        return {
            "status": "failed",
            "sent": [],
            "errors": {"discord": "delivery failed"},
            "event_type": "daily_brief",
        }

    monkeypatch.setattr("reports.daily_brief.dispatch_event", fake_dispatch)

    result = run_db_test(run_daily_brief_slot("eod"))
    assert result["status"] == "failed"
    assert result["slot"] == "eod"

    async def check():
        db = await get_db()
        try:
            return await get_sync_state_value(db, "daily_brief:last_eod_end")
        finally:
            await db.close()

    assert run_db_test(check()) is None


def test_template_headline_mentions_unmapped_share():
    rows = [{"severity": "MEDIUM", "cpe_matches": "", "affected_products": ""}] * 6
    rows.append({"severity": "CRITICAL", "cpe_matches": '[{"product":"gitea"}]', "affected_products": ""})
    market = cluster_published(rows)
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-26 18:00",
        window_end_local="2026-08-27 18:00",
        generated_local="2026-08-27 18:00",
        headline="",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        market=market,
    )
    text = template_headline(brief)
    assert "gitea" in text.lower()
    assert "unanalyzed led volume" not in text.lower()
    assert "Unmapped" in text or "no product mapped" in text.lower()


def test_headlines_from_snapshot_in_window(db_env):
    from database import get_db, set_feed_cache

    end = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)
    snapshot = {
        "cards": [
            {
                "kind": "news",
                "source": "Krebs on Security",
                "sourceId": "krebs",
                "title": "CISA adds VPN flaws to KEV",
                "url": "https://kreb.example/a",
                "publishedAt": "2026-08-27T10:00:00+00:00",
            },
            {
                "kind": "atlas",
                "source": "MITRE ATLAS",
                "title": "Ignore me",
                "url": "https://atlas.example",
                "publishedAt": "2026-08-27T11:00:00+00:00",
            },
            {
                "kind": "news",
                "source": "The Hacker News",
                "sourceId": "hackernews",
                "title": "Old",
                "url": "https://thn.example/old",
                "publishedAt": "2026-08-20T10:00:00+00:00",
            },
        ]
    }

    async def _go():
        db = await get_db()
        try:
            await set_feed_cache(db, "incident_feed:snapshot", snapshot)
            await db.commit()
            return await collect_daily_brief(
                db,
                slot="eod",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
        finally:
            await db.close()

    brief = run_db_test(_go())
    assert len(brief.headlines) == 1
    assert brief.headlines[0]["source"] == "Krebs on Security"
    assert brief_to_payload(brief)["headlines"][0]["title"].startswith("CISA adds")
    assert brief.advisories == []


def test_embed_uses_orange_and_human_fields():
    import json
    from reports.daily_brief import DISCORD_EMBED_COLOR, format_daily_brief_embed

    market = cluster_published(
        [
            {"severity": "CRITICAL", "cpe_matches": '[{"product":"gitea"}]', "affected_products": ""},
            {"severity": "LOW", "cpe_matches": "", "affected_products": ""},
        ]
    )
    brief = DailyBrief(
        slot="eod",
        tz_name="Asia/Kolkata",
        window_start_local="2026-08-26 21:15",
        window_end_local="2026-08-27 21:15",
        generated_local="2026-08-27 21:15",
        headline="2 published. gitea ranked first.",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS} | {"critical_high_new": 1, "ops_issues": 1},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[
            {
                "id": "kev_metadata_sync",
                "reason": "KEV request failed",
                "error_class": "job_error",
            }
        ],
        market=market,
        headlines=[
            {"source": "Krebs on Security", "title": "VPN KEV", "url": "https://kreb.example/a"}
        ],
        advisories=[],
    )
    embeds = format_daily_brief_embed(brief)
    assert len(embeds) == 1
    emb = embeds[0]
    assert emb["color"] == DISCORD_EMBED_COLOR == 0xE85533
    assert emb["title"] == "End of day"
    names = [field["name"] for field in emb["fields"]]
    assert "At a glance" in names
    assert "Coverage" in names
    assert "Headlines" in names
    blob = json.dumps(emb)
    assert "// HEADLINE" not in blob
    assert "Unmapped" in blob
    assert "KEV Metadata Sync" in blob


def test_html_escapes_headline_title():
    from reports.daily_brief import format_daily_brief_html

    brief = DailyBrief(
        slot="standup",
        tz_name="UTC",
        window_start_local="a",
        window_end_local="b",
        generated_local="c",
        headline="Quiet window.",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        headlines=[{"source": "THN", "title": "Foo <script> x", "url": "https://x.example"}],
        advisories=[],
    )
    html = format_daily_brief_html(brief)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Morning briefing" in html


def test_html_overflow_drops_sections_without_slicing_entities():
    from reports.daily_brief import format_daily_brief_html

    long_reason = "failed & retry <limit> " * 40
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-26 18:00",
        window_end_local="2026-08-27 18:00",
        generated_local="2026-08-27 18:00",
        headline="Quiet window.",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS} | {"kev_new": 8, "ops_issues": 5},
        kev=[
            {"cve_id": f"CVE-2026-{i:04d}", "reason": long_reason, "severity": "HIGH"}
            for i in range(8)
        ],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[
            {
                "id": f"job-{i}",
                "reason": long_reason,
                "error_class": "job_error",
            }
            for i in range(5)
        ],
        headlines=[
            {
                "source": "THN",
                "title": "Ampersand & angle <tag> " * 30,
                "url": "https://x.example",
            }
        ],
        advisories=[],
    )
    html = format_daily_brief_html(brief)
    assert html.count("<b>") == html.count("</b>")
    assert "Generated 2026-08-27 18:00 UTC" in html
    assert "…" not in html
    assert "&am;" not in html
    leftover = html
    while "&" in leftover:
        idx = leftover.index("&")
        chunk = leftover[idx : idx + 5]
        assert chunk.startswith("&amp;") or chunk.startswith("&lt;") or chunk.startswith("&gt;")
        leftover = leftover[idx + 1 :]

