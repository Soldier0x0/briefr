"""CORR-PR-13: correlation quality metrics snapshot."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation.metrics import snapshot_correlation_metrics
from database import get_db, init_db
from tests.conftest import run_db_test


def test_correlation_metrics_snapshot_counts(tmp_path, monkeypatch):
    db_path = tmp_path / "corr_metrics.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, published)
                VALUES ('CVE-2024-9001', 'Metrics test', '2024-01-01')
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_campaigns (
                    campaign_id, primary_pulse_id, label, confidence,
                    member_count, lifecycle, independent_sources
                ) VALUES ('camp-m', 'p1', 'Test', 'high', 1, 'active', 2)
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_campaign_members (campaign_id, cve_id, role)
                VALUES ('camp-m', 'CVE-2024-9001', 'anchor')
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_suppressions (
                    cve_id, scope, scope_key, reason, created_at
                ) VALUES ('CVE-2024-9001', 'campaign_id', 'camp-x', 'fp', datetime('now'))
                """
            )
            await db.execute(
                """
                INSERT INTO correlation_feedback (
                    cve_id, scope, scope_key, verdict, reason, created_at
                ) VALUES ('CVE-2024-9001', 'campaign_id', 'camp-m', 'confirm', 'ok', datetime('now'))
                """
            )
            await db.execute(
                """
                INSERT INTO otx_pulse_iocs (pulse_id, ioc_type, ioc_value, fetched_at)
                VALUES ('p1', 'IPv4', '1.2.3.4', datetime('now')),
                       ('p1', 'domain', 'evil.test', datetime('now'))
                """
            )
            await db.execute(
                """
                INSERT INTO ioc_degree (ioc_type, ioc_value, cve_count, pulse_count, computed_at)
                VALUES ('IP', '1.2.3.4', 60, 10, datetime('now'))
                """
            )
            await db.commit()

            row = await snapshot_correlation_metrics(db)
            await db.commit()

            assert row["day"] == date.today().isoformat()
            assert row["suppressions_30d"] >= 1
            assert row["feedback_confirm_30d"] >= 1
            assert row["campaigns_active"] >= 1
            assert row["weak_edge_ratio"] == 0.5
            assert row["hub_suppressed_edge_count"] >= 1
            assert row["avg_independent_sources"] == 2.0
        finally:
            await db.close()

    run_db_test(_run())
